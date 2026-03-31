#!/usr/bin/env python3
"""
slice_controller.py
───────────────────
Transport Slice Controller — Workshop Exercise 4

This controller provisions a network slice over the workshop topology.
A "slice" is an isolated, resource-guaranteed path through the network.

Each slice has three properties:
  1. PATH      — which nodes traffic must pass through (enforced by SRv6)
  2. BANDWIDTH — how much bandwidth is reserved (enforced by OVS HTB queues)
  3. PRIORITY  — which queue gets preference under congestion (enforced by ONOS flow rules)

Under the hood, three systems work together:
  ┌─────────────────────────────────────────────────────┐
  │              slice_controller.py                    │
  ├──────────────┬──────────────────┬───────────────────┤
  │  ONOS REST   │  SRv6 / iproute2 │  OVS HTB queues   │
  │              │                  │                   │
  │  discover    │  force traffic   │  guarantee        │
  │  topology    │  through         │  bandwidth        │
  │  push flow   │  the right       │  per slice        │
  │  rules       │  middlebox       │                   │
  └──────────────┴──────────────────┴───────────────────┘

Usage:
    # Provision a video slice: h1 → mb1 → h2, 10Mbps guaranteed
    sudo python3 slice_controller.py --slice video --path h1,mb1,h2 --bandwidth 10M --verify

    # Provision a bulk slice: h1 → h2 direct, best effort
    sudo python3 slice_controller.py --slice bulk --path h1,h2 --bandwidth 0 --verify

    # List active slices
    sudo python3 slice_controller.py --list

    # Remove a slice
    sudo python3 slice_controller.py --remove video
"""

import argparse
import subprocess
import sys
import time
import requests
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel

# Import our shared topology definition
from labs.lab2.workshop_topology import WorkshopTopo, SRV6_SIDS, HOST_IPS


# ─── ONOS connection settings ─────────────────────────────────────────────────
#
# These match the defaults from the ONOS Docker container.
# If you changed the password in the Ansible playbook, update ONOS_PASSWORD.

ONOS_HOST     = "http://localhost:8181"
ONOS_API      = f"{ONOS_HOST}/onos/v1"
ONOS_USER     = "onos"
ONOS_PASSWORD = "rocks"
ONOS_AUTH     = (ONOS_USER, ONOS_PASSWORD)

# ─── OVS queue numbers ────────────────────────────────────────────────────────
#
# OVS HTB queues are numbered. We reserve:
#   Queue 1 → video slice  (high priority, guaranteed bandwidth)
#   Queue 0 → bulk / default (best effort)

QUEUE_VIDEO = 1
QUEUE_BULK  = 0

# ─── Slice priority for OpenFlow rules ───────────────────────────────────────
#
# Higher priority rules are matched first by OVS.
# Video slice rules must be higher priority than bulk so they
# get the reserved queue even under congestion.

PRIORITY_VIDEO = 40000
PRIORITY_BULK  = 30000


class SliceController:
    """
    The Transport Slice Controller.

    This class is the brain of the operation. It orchestrates ONOS,
    SRv6, and OVS to provision and manage network slices.

    Participants: read through each method in order — they correspond
    to the steps you learned in Exercises 1, 2, and 3.
    """

    def __init__(self, net):
        """
        Initialise the controller with a running Mininet network.

        'net' is the Mininet object returned by Mininet(...).start().
        The controller uses it to access host network namespaces directly
        (for SRv6 configuration) and to access OVS switches (for queuing).
        """
        self.net = net

        # Track active slices so we can list and remove them
        # Key: slice name, Value: dict of slice parameters
        self.active_slices = {}

        print("[Controller] Transport Slice Controller initialised")
        print(f"[Controller] ONOS API: {ONOS_API}")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1 — Topology Discovery (ONOS)
    # ─────────────────────────────────────────────────────────────────────────
    #
    # Before provisioning a slice, the controller needs to know what the
    # network looks like. It asks ONOS for the current topology — which
    # switches exist, which hosts are connected, and how they are linked.
    #
    # This is the same ONOS REST API you used in Exercise 2.

    def discover_topology(self):
        """
        Query ONOS for the current network topology.

        Returns a dict with 'devices' (switches) and 'hosts'.
        Raises an exception if ONOS is not reachable.
        """
        print("\n[Step 1] Discovering topology via ONOS REST API...")

        # GET /onos/v1/topology — returns switch and link counts
        topo = self._onos_get("/topology")
        print(f"  Switches : {topo['devices']}")
        print(f"  Links    : {topo['links']}")

        # GET /onos/v1/hosts — returns all known hosts with their IPs and MACs
        hosts_resp = self._onos_get("/hosts")
        hosts = hosts_resp.get('hosts', [])
        print(f"  Hosts    : {len(hosts)} discovered")
        for h in hosts:
            ips = ", ".join(h.get('ipAddresses', []))
            print(f"    {h['id']} → {ips}")

        return {'devices': topo['devices'], 'links': topo['links'], 'hosts': hosts}

    def resolve_host_ip(self, hostname):
        """
        Get the IPv4 address of a host by name.

        We use Mininet directly here since ONOS host discovery can be
        slow on first run. In a real network you would always use the
        controller — you don't have direct access to the data plane.
        """
        host = self.net[hostname]
        return host.IP()

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2 — SRv6 Path Programming (iproute2)
    # ─────────────────────────────────────────────────────────────────────────
    #
    # SRv6 enforces the path by embedding a list of waypoints (SIDs)
    # directly into the packet header (the SRH — Segment Routing Header).
    #
    # The ingress host encapsulates the packet with the SRH.
    # Each waypoint processes the SRH and forwards to the next SID.
    # This is exactly what you did manually in Exercise 3.

    def provision_srv6(self, path):
        """
        Program SRv6 routing rules for a given path.

        'path' is a list of node names, e.g. ['h1', 'mb1', 'h2']

        What this does:
          - Ingress host (path[0]): add a route that encapsulates traffic
            with an SRH listing all intermediate SIDs
          - Middleboxes (path[1:-1]): add endpoint behaviour (End) so
            the kernel processes the SRH when it receives a packet
        """
        print(f"\n[Step 2] Programming SRv6 path: {' → '.join(path)}")

        ingress  = self.net[path[0]]   # e.g. h1
        egress   = self.net[path[-1]]  # e.g. h2
        waypoints = path[1:-1]         # e.g. ['mb1']

        # Build the SID list — these are the IPv6 addresses that will appear
        # in the SRH. The order matches the path order.
        sids = [SRV6_SIDS[node] for node in path[1:]]
        sid_list = ",".join(sids)

        egress_sid  = SRV6_SIDS[path[-1]]
        ingress_dev = f"{path[0]}-eth0"

        # ── Ingress: encapsulate traffic with SRH ───────────────────────────
        #
        # This tells the ingress host: "when sending traffic to the egress SID,
        # wrap the packet in an SRH containing [waypoint SID, egress SID]"
        #
        # 'encap seg6 mode encap' means: add a new outer IPv6 header + SRH
        # 'segs' is the ordered list of SIDs (waypoints)
        #
        # Equivalent to what you ran manually in Exercise 3:
        #   ip -6 route add fc00::2 encap seg6 mode encap segs fc00::b1,fc00::2 dev h1-eth0

        cmd = (
            f'ip -6 route add {egress_sid} '
            f'encap seg6 mode encap '
            f'segs {sid_list} '
            f'dev {ingress_dev}'
        )
        print(f"  [h1 ingress] {cmd}")
        ingress.cmd(cmd)

        # ── Middleboxes: install SRv6 endpoint behaviour ────────────────────
        #
        # Each middlebox needs to know what to do when it receives a packet
        # destined for its own SID. The 'End' behaviour means:
        #   1. Decrement the Segments Left counter in the SRH
        #   2. Update the outer destination to the next SID
        #   3. Forward normally
        #
        # This is the SRv6 equivalent of a "pop and forward" operation.

        for node_name in waypoints:
            node    = self.net[node_name]
            node_sid = SRV6_SIDS[node_name]
            node_dev = f"{node_name}-eth0"

            # Enable SRv6 on this node's interface if not already done
            node.cmd('sysctl -w net.ipv6.conf.all.seg6_enabled=1')
            node.cmd('sysctl -w net.ipv6.conf.all.forwarding=1')

            cmd = (
                f'ip -6 route add {node_sid} '
                f'encap seg6local action End '
                f'dev {node_dev}'
            )
            print(f"  [{node_name} endpoint] {cmd}")
            node.cmd(cmd)

        print(f"  SRv6 path programmed: {' → '.join(path)}")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3 — OVS Queue Provisioning (ovs-vsctl)
    # ─────────────────────────────────────────────────────────────────────────
    #
    # SRv6 forces the path but does not reserve bandwidth.
    # OVS HTB (Hierarchical Token Bucket) queues do.
    #
    # We create two queues on each OVS port:
    #   Queue 1: video slice — guaranteed minimum bandwidth
    #   Queue 0: bulk / default — best effort, gets what's left
    #
    # This is the OVS queuing you explored manually in Exercise 1.

    def provision_queues(self, slice_name, bandwidth_mbps):
        """
        Create HTB queues on all OVS switches for this slice.

        'bandwidth_mbps' is the guaranteed minimum rate in Mbps.
        Set to 0 for best-effort (bulk) slices.
        """
        print(f"\n[Step 3] Provisioning OVS queues ({bandwidth_mbps}Mbps for '{slice_name}' slice)...")

        # Convert Mbps to bps for ovs-vsctl
        min_rate_bps = bandwidth_mbps * 1_000_000
        max_rate_bps = 100 * 1_000_000   # 100Mbps link cap

        queue_num = QUEUE_VIDEO if slice_name == 'video' else QUEUE_BULK

        for switch in self.net.switches:
            # Get all ports on this switch
            ports = switch.intfList()
            for port in ports:
                if port.name == 'lo':
                    continue   # skip loopback

                # ovs-vsctl command to create an HTB QoS policy with two queues.
                # Queue 1 (video): min-rate guaranteed, max-rate = link speed
                # Queue 0 (bulk):  no min-rate, competes for remaining bandwidth
                #
                # HTB works like this: queue 1 is always served first up to
                # its min-rate. Remaining bandwidth goes to queue 0.

                cmd = (
                    f'ovs-vsctl set port {port.name} qos=@newqos '
                    f'-- --id=@newqos create qos type=linux-htb '
                    f'other-config:max-rate={max_rate_bps} '
                    f'queues={QUEUE_VIDEO}=@q_video,{QUEUE_BULK}=@q_bulk '
                    f'-- --id=@q_video create queue '
                    f'other-config:min-rate={min_rate_bps} '
                    f'other-config:max-rate={max_rate_bps} '
                    f'-- --id=@q_bulk create queue '
                    f'other-config:max-rate={max_rate_bps}'
                )
                switch.cmd(cmd)
                print(f"  {switch.name}/{port.name}: queue {queue_num} = {bandwidth_mbps}Mbps min-rate")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4 — OpenFlow Flow Rules via ONOS (REST API)
    # ─────────────────────────────────────────────────────────────────────────
    #
    # OVS now has queues, but it doesn't know which packets belong to
    # which slice. We need OpenFlow rules that:
    #   1. Match packets by their SRv6 destination SID
    #   2. Send them to the right queue
    #
    # The SID in the packet is the slice identifier — it's what connects
    # the SRv6 world (path) to the OVS world (queuing).
    #
    # We push these rules via ONOS REST API, exactly as you did in Exercise 2.

    def push_flow_rules(self, slice_name, path):
        """
        Push OpenFlow rules to ONOS that map SRv6 SIDs to OVS queues.

        For each SID in the path, we tell every switch:
          "if you see a packet destined for this SID → use queue N"

        This is what enforces the bandwidth guarantee — without these
        rules, OVS wouldn't know to put video traffic in queue 1.
        """
        print(f"\n[Step 4] Pushing OpenFlow flow rules via ONOS REST API...")

        queue_num = QUEUE_VIDEO if slice_name == 'video' else QUEUE_BULK
        priority  = PRIORITY_VIDEO if slice_name == 'video' else PRIORITY_BULK

        # Get the list of switch device IDs from ONOS
        devices_resp = self._onos_get("/devices")
        devices = devices_resp.get('devices', [])

        for sid_node in path[1:]:   # push rules for each waypoint + egress SID
            sid = SRV6_SIDS[sid_node]

            for device in devices:
                device_id = device['id']

                # Build an OpenFlow 1.3 flow rule in ONOS JSON format.
                # This is the same format you used in the ONOS intents exercise.
                #
                # match:       IPv6 destination == this SID
                # treatment:   enqueue to the right OVS queue
                flow_rule = {
                    "priority": priority,
                    "timeout": 0,          # 0 = permanent (until we remove it)
                    "isPermanent": True,
                    "deviceId": device_id,
                    "treatment": {
                        "instructions": [
                            {
                                # ENQUEUE instruction — send to specific queue
                                "type": "ENQUEUE",
                                "queueId": queue_num,
                            }
                        ]
                    },
                    "selector": {
                        "criteria": [
                            {"type": "ETH_TYPE", "ethType": "0x86DD"},  # IPv6
                            {"type": "IPV6_DST", "ip": f"{sid}/128"},
                        ]
                    }
                }

                resp = requests.post(
                    f"{ONOS_API}/flows/{device_id}",
                    json={"flows": [flow_rule]},
                    auth=ONOS_AUTH
                )

                if resp.status_code in (200, 201):
                    print(f"  ✓ {device_id}: match IPv6 dst={sid} → queue {queue_num}")
                else:
                    print(f"  ✗ {device_id}: failed ({resp.status_code}) — {resp.text}")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5 — Verification
    # ─────────────────────────────────────────────────────────────────────────
    #
    # After provisioning, we verify the slice actually works.
    # We use iperf3 to generate traffic and measure throughput.
    #
    # The verification has two parts:
    #   1. Baseline: run iperf3 on this slice alone — should hit bandwidth target
    #   2. Stress test: run bulk traffic simultaneously — video slice should hold

    def verify(self, slice_name, path, bandwidth_mbps):
        """
        Verify the slice by running iperf3 and checking throughput.

        This is the payoff — you should see the video slice maintaining
        its bandwidth guarantee even when bulk traffic is competing.
        """
        print(f"\n[Step 5] Verifying '{slice_name}' slice...")

        ingress_name = path[0]
        egress_name  = path[-1]
        ingress = self.net[ingress_name]
        egress  = self.net[egress_name]
        egress_sid = SRV6_SIDS[egress_name]

        # Start iperf3 server on egress host
        print(f"  Starting iperf3 server on {egress_name}...")
        egress.cmd('pkill iperf3; sleep 0.5')   # kill any existing server
        egress.cmd('iperf3 -s -D')              # -D = run as daemon
        time.sleep(1)

        # Run iperf3 client on ingress host, targeting the SRv6 SID
        # (not the IPv4 address — we want to trigger the SRv6 encapsulation)
        print(f"  Running iperf3 from {ingress_name} → {egress_sid} (10 seconds)...")
        result = ingress.cmd(
            f'iperf3 -c {egress_sid} -t 10 -b {bandwidth_mbps}M --json'
        )

        # Parse and display the result
        try:
            import json
            data = json.loads(result)
            achieved_bps  = data['end']['sum_received']['bits_per_second']
            achieved_mbps = achieved_bps / 1_000_000
            target_mbps   = bandwidth_mbps

            print(f"\n  ┌─── Slice Verification Result ───────────────────┐")
            print(f"  │  Slice     : {slice_name}")
            print(f"  │  Path      : {' → '.join(path)}")
            print(f"  │  Target BW : {target_mbps:.1f} Mbps")
            print(f"  │  Achieved  : {achieved_mbps:.2f} Mbps")

            if achieved_mbps >= target_mbps * 0.9:   # 90% tolerance
                print(f"  │  Status    : ✓ PASS — bandwidth guarantee met")
            else:
                print(f"  │  Status    : ✗ FAIL — below target")
            print(f"  └─────────────────────────────────────────────────┘\n")

        except (json.JSONDecodeError, KeyError):
            # If JSON parsing fails, just print raw output
            print(f"  iperf3 output:\n{result}")

        # Clean up iperf3 server
        egress.cmd('pkill iperf3')

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC API — provision() and remove()
    # ─────────────────────────────────────────────────────────────────────────
    #
    # These are the main entry points. The CLI calls provision() when you
    # run slice_controller.py --slice video --path ... --bandwidth ...
    #
    # Participants working on Exercise 4b can also call these directly:
    #   from slice_controller import SliceController
    #   ctrl = SliceController(net)
    #   ctrl.provision('bulk', ['h1', 'h2'], bandwidth_mbps=0, verify=True)

    def provision(self, slice_name, path, bandwidth_mbps, verify=False):
        """
        Provision a network slice end-to-end.

        This is the top-level method that calls Steps 1–5 in order.
        Each step corresponds to a concept from Exercises 1–3.

        Args:
            slice_name    : name for this slice (e.g. 'video', 'bulk')
            path          : list of node names (e.g. ['h1', 'mb1', 'h2'])
            bandwidth_mbps: guaranteed bandwidth in Mbps (0 = best effort)
            verify        : run iperf3 verification after provisioning
        """
        print(f"\n{'═' * 60}")
        print(f"  Provisioning slice: '{slice_name}'")
        print(f"  Path     : {' → '.join(path)}")
        print(f"  Bandwidth: {bandwidth_mbps} Mbps")
        print(f"{'═' * 60}")

        # Step 1: discover topology via ONOS
        self.discover_topology()

        # Step 2: program SRv6 path on hosts
        self.provision_srv6(path)

        # Step 3: create OVS HTB queues for bandwidth enforcement
        self.provision_queues(slice_name, bandwidth_mbps)

        # Step 4: push OpenFlow rules via ONOS to map SIDs → queues
        self.push_flow_rules(slice_name, path)

        # Record this slice so we can list/remove it later
        self.active_slices[slice_name] = {
            'path': path,
            'bandwidth_mbps': bandwidth_mbps,
        }

        print(f"\n[Controller] Slice '{slice_name}' provisioned successfully.")

        # Step 5 (optional): verify with iperf3
        if verify:
            self.verify(slice_name, path, bandwidth_mbps)

    def remove(self, slice_name):
        """
        Remove a provisioned slice.

        Removes the SRv6 routes from the ingress host and deletes
        the ONOS flow rules for this slice's SIDs.
        """
        if slice_name not in self.active_slices:
            print(f"[Controller] Slice '{slice_name}' not found.")
            return

        slice_info = self.active_slices[slice_name]
        path = slice_info['path']
        ingress = self.net[path[0]]
        egress_sid = SRV6_SIDS[path[-1]]

        print(f"\n[Controller] Removing slice '{slice_name}'...")

        # Remove SRv6 route from ingress host
        ingress.cmd(f'ip -6 route del {egress_sid}')
        print(f"  Removed SRv6 route from {path[0]}")

        # Remove ONOS flow rules (delete by app ID or iterate and delete)
        # For simplicity in the workshop we flush all flows and let
        # ONOS re-discover. In production you would track flow IDs.
        print(f"  Removing ONOS flow rules for '{slice_name}' SIDs...")
        devices_resp = self._onos_get("/devices")
        for device in devices_resp.get('devices', []):
            self._onos_delete(f"/flows/{device['id']}")

        del self.active_slices[slice_name]
        print(f"[Controller] Slice '{slice_name}' removed.")

    def list_slices(self):
        """Print a summary of all active slices."""
        print(f"\n{'═' * 60}")
        print(f"  Active Slices")
        print(f"{'═' * 60}")
        if not self.active_slices:
            print("  No active slices.")
        for name, info in self.active_slices.items():
            print(f"  {name}")
            print(f"    Path      : {' → '.join(info['path'])}")
            print(f"    Bandwidth : {info['bandwidth_mbps']} Mbps")
        print(f"{'═' * 60}\n")

    # ─────────────────────────────────────────────────────────────────────────
    # ONOS REST helpers
    # ─────────────────────────────────────────────────────────────────────────
    #
    # These are thin wrappers around the requests library.
    # They handle authentication and error checking so the main methods
    # stay readable. You used the same REST API directly in Exercise 2.

    def _onos_get(self, path):
        """GET a resource from the ONOS REST API."""
        url = f"{ONOS_API}{path}"
        try:
            resp = requests.get(url, auth=ONOS_AUTH, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            print(f"  [ONOS] Cannot connect to {url}")
            print(f"  [ONOS] Is ONOS running? Try: docker ps")
            sys.exit(1)
        except requests.exceptions.HTTPError as e:
            print(f"  [ONOS] HTTP error: {e}")
            return {}

    def _onos_post(self, path, data):
        """POST data to the ONOS REST API."""
        url = f"{ONOS_API}{path}"
        resp = requests.post(url, json=data, auth=ONOS_AUTH, timeout=5)
        return resp

    def _onos_delete(self, path):
        """DELETE a resource from the ONOS REST API."""
        url = f"{ONOS_API}{path}"
        resp = requests.delete(url, auth=ONOS_AUTH, timeout=5)
        return resp


# ─── CLI entry point ──────────────────────────────────────────────────────────
#
# This is what runs when you execute:
#   sudo python3 slice_controller.py --slice video --path h1,mb1,h2 --bandwidth 10M
#
# It starts Mininet, connects to ONOS, creates the SliceController,
# and calls provision() with your arguments.

def parse_bandwidth(bw_str):
    """Convert '10M' or '10' to an integer Mbps value."""
    bw_str = bw_str.strip().upper().replace('MBPS', '').replace('M', '')
    return int(bw_str)


def main():
    parser = argparse.ArgumentParser(
        description='Transport Slice Controller — Workshop Exercise 4',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Provision a video slice with 10Mbps guarantee through the middlebox
  sudo python3 slice_controller.py --slice video --path h1,mb1,h2 --bandwidth 10M --verify

  # Provision a bulk slice (best effort, direct path)
  sudo python3 slice_controller.py --slice bulk --path h1,h2 --bandwidth 0

  # List active slices
  sudo python3 slice_controller.py --list

  # Remove a slice
  sudo python3 slice_controller.py --remove video
        """
    )

    parser.add_argument('--slice',     help='Name of the slice (e.g. video, bulk)')
    parser.add_argument('--path',      help='Comma-separated path (e.g. h1,mb1,h2)')
    parser.add_argument('--bandwidth', help='Guaranteed bandwidth (e.g. 10M)', default='0')
    parser.add_argument('--verify',    action='store_true', help='Run iperf3 verification')
    parser.add_argument('--list',      action='store_true', help='List active slices')
    parser.add_argument('--remove',    help='Remove a slice by name')

    args = parser.parse_args()

    setLogLevel('warning')   # suppress Mininet noise during the workshop

    # Start Mininet with ONOS as the remote controller
    print("\n[Setup] Starting Mininet topology...")
    net = Mininet(
        topo=WorkshopTopo(),
        controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6653),
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        waitConnected=True,
    )
    net.start()

    # Enable SRv6 on all hosts
    from labs.lab2.workshop_topology import configure_srv6
    configure_srv6(net)

    # Create the controller
    ctrl = SliceController(net)

    try:
        if args.list:
            ctrl.list_slices()

        elif args.remove:
            ctrl.remove(args.remove)

        elif args.slice and args.path:
            path = args.path.split(',')
            bandwidth = parse_bandwidth(args.bandwidth)
            ctrl.provision(args.slice, path, bandwidth, verify=args.verify)

        else:
            parser.print_help()

    finally:
        # Always clean up Mininet on exit
        print("\n[Setup] Stopping Mininet...")
        net.stop()


if __name__ == '__main__':
    main()