#!/usr/bin/env python3
"""
Contention Demo with OVS Queues – ONOS Edition
================================================
Topology:
    h1 (10.0.0.1) ──┐
                    s1 ──[10 Mbps]── s2 ── h2 (10.0.0.2)
    h3 (10.0.0.3) ──┘

Controller: ONOS running in Docker on localhost:6653 (OpenFlow 1.3)
Required ONOS apps: openflow, fwd, proxyarp

Bottleneck: s1 -> s2 link at 10 Mbps

Demo phases:
Phase 1: h1->h2 at 8 Mbps              (no contention, ~8 Mbps)
  Phase 2: h3->h2 surges at 10 Mbps      (contention! h1 drops to ~3-4 Mbps)
  Phase 3: OVS queues provisioned        (h1 guaranteed 8 Mbps again)

Usage:
    sudo python3 contention_demo_onos.py [--onos-ip IP] [--onos-rest-port PORT]

Defaults:
    --onos-ip        127.0.0.1
    --onos-rest-port 8181
    --onos-user      onos
    --onos-pass      rocks
"""

import sys
import time
import argparse
import json
import subprocess

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    print("\n✗  Python 'requests' library not found for this Python interpreter.")
    print(f"   Fix: sudo pip3 install requests --break-system-packages")
    print(f"   Then re-run with sudo.\n")
    sys.exit(1)

from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI


# ─── ONOS REST helpers ────────────────────────────────────────────────────────

class ONOSClient:
    def __init__(self, ip, rest_port, user, password):
        self.base = f"http://{ip}:{rest_port}/onos/v1"
        self.auth = HTTPBasicAuth(user, password)
        self.headers = {"Content-Type": "application/json",
                        "Accept":       "application/json"}

    def get(self, path):
        # No Content-Type on GET — ONOS returns 415 if it's present
        r = requests.get(f"{self.base}{path}", auth=self.auth,
                         headers={"Accept": "application/json"}, timeout=5)
        r.raise_for_status()
        return r.json()

    def post(self, path, payload):
        r = requests.post(f"{self.base}{path}", auth=self.auth,
                          headers=self.headers,
                          data=json.dumps(payload), timeout=5)
        r.raise_for_status()
        return r

    def delete(self, path):
        r = requests.delete(f"{self.base}{path}", auth=self.auth,
                            headers=self.headers, timeout=5)
        r.raise_for_status()
        return r

    def check_alive(self):
        try:
            self.get("/devices")
            return True, None
        except Exception as e:
            return False, str(e)

    def wait_for_devices(self, expected=2, timeout=30):
        """Block until ONOS sees at least `expected` devices."""
        info(f"*** Waiting for ONOS to discover {expected} devices ")
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                devs = self.get("/devices")
                count = len(devs.get("devices", []))
                info(f"({count}/{expected}) ")
                if count >= expected:
                    info("✓\n")
                    return True
            except Exception:
                pass
            time.sleep(2)
        info("\n!!! Timed out waiting for devices\n")
        return False




# ─── Topology ─────────────────────────────────────────────────────────────────

def build_topology(net):
    info("*** Adding hosts\n")
    h1 = net.addHost("h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01")
    h2 = net.addHost("h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02")
    h3 = net.addHost("h3", ip="10.0.0.3/24", mac="00:00:00:00:00:03")

    info("*** Adding switches\n")
    s1 = net.addSwitch("s1", cls=OVSKernelSwitch, protocols="OpenFlow13")
    s2 = net.addSwitch("s2", cls=OVSKernelSwitch, protocols="OpenFlow13")

    info("*** Adding links\n")
    net.addLink(h1, s1, cls=TCLink, bw=100, delay="1ms")
    net.addLink(h3, s1, cls=TCLink, bw=100, delay="1ms")
    net.addLink(h2, s2, cls=TCLink, bw=100, delay="1ms")
    # *** BOTTLENECK ***
    net.addLink(s1, s2, cls=TCLink, bw=10, delay="5ms")

    return h1, h2, h3, s1, s2


# ─── OVS queue helpers ────────────────────────────────────────────────────────

def get_iface_facing(switch, peer_name):
    """Return the interface name on `switch` that connects to `peer_name`."""
    for intf in switch.intfList():
        if intf.link:
            other = (intf.link.intf2 if intf.link.intf1 == intf
                     else intf.link.intf1)
            if other.node.name == peer_name:
                return intf.name
    raise RuntimeError(f"No link found between {switch.name} and {peer_name}")


def get_ofport(switch, iface):
    """Return the OpenFlow port number for an interface."""
    return switch.cmd(f"ovs-vsctl get Interface {iface} ofport").strip()


def setup_ovs_queues(s1):
    """
    Create two HTB queues on the s1->s2 bottleneck port:
      Queue 0 : best-effort  (gets whatever h1 doesn't use)
      Queue 1 : h1 reserved  – guaranteed 8 Mbps, max 8 Mbps
    Returns (iface_name, ofport) for use in ONOS flow push.
    """
    iface = get_iface_facing(s1, "s2")
    info(f"\n*** Provisioning OVS queues on {iface} (s1→s2 bottleneck)\n")

    # Wipe any existing QoS first
    s1.cmd(f"ovs-vsctl clear port {iface} qos")
    s1.cmd("ovs-vsctl --all destroy qos 2>/dev/null; true")
    s1.cmd("ovs-vsctl --all destroy queue 2>/dev/null; true")

    # Create QoS + queues
    out = s1.cmd(
        f'ovs-vsctl set port {iface} qos=@newqos -- '
        f'--id=@newqos create qos type=linux-htb '
        f'other-config:max-rate=10000000 '           # total 10 Mbps
        f'queues:0=@q0 queues:1=@q1 -- '
        f'--id=@q0 create queue '
        f'other-config:min-rate=1000000 '            # Q0 best-effort min
        f'other-config:max-rate=10000000 '           # Q0 up to full 10M
        f'other-config:burst=125000 -- '             # 125 KB burst cap
        f'--id=@q1 create queue '
        f'other-config:min-rate=8000000 '            # Q1 guaranteed 8 Mbps
        f'other-config:max-rate=8000000 '            # Q1 capped at 8 Mbps
        f'other-config:burst=62500'                  # 62 KB burst — prevents TCP cwnd overflow
    )
    info(f"    ovs-vsctl output: {out.strip()}\n")

    ofport = get_ofport(s1, iface)
    info(f"    Bottleneck port ofport={ofport}\n")
    info( "    Queue 0 → best-effort (h3 and others)\n")
    info( "    Queue 1 → h1 guaranteed 8 Mbps\n")
    return iface, ofport


def teardown_ovs_queues(s1):
    try:
        iface = get_iface_facing(s1, "s2")
        info(f"\n*** Removing QoS from {iface}\n")
        s1.cmd(f"ovs-vsctl clear port {iface} qos")
        s1.cmd("ovs-vsctl --all destroy qos 2>/dev/null; true")
        s1.cmd("ovs-vsctl --all destroy queue 2>/dev/null; true")
    except Exception as e:
        info(f"    (teardown warning: {e})\n")


# ─── iperf helpers ────────────────────────────────────────────────────────────
# iperf3 only accepts one client at a time, so each sender needs its own
# server instance on a distinct port.

H1_PORT = 5201
H3_PORT = 5202


def start_iperf_server(h2):
    """Start two iperf3 server instances on h2 — one per sender."""
    h2.cmd("pkill -f iperf3 2>/dev/null; true")
    time.sleep(0.3)
    h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
    h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
    time.sleep(0.5)
    info(f"*** iperf3 servers ready on h2  port {H1_PORT} (for h1)  port {H3_PORT} (for h3)\n")


def run_iperf_client(host, server_ip, bandwidth_mbps, port, duration=60, tag="", udp=False):
    udp_flag = "-u " if udp else ""
    cmd = (
        f"iperf3 -c {server_ip} -p {port} {udp_flag}-b {bandwidth_mbps}M "
        f"-t {duration} --forceflush -i 1 "
        f"2>&1 | tee /tmp/iperf_{tag}.log &"
    )
    host.cmd(cmd)


# ─── Interactive demo ─────────────────────────────────────────────────────────

def interactive_demo(net, h1, h2, h3, s1, s2, onos, onos_ip):
    sep = "=" * 62

    print(f"\n{sep}")
    print("  CONTENTION DEMO – ONOS Edition")
    print(sep)
    print(f"""
Topology:
    h1 (10.0.0.1) ──┐
                    s1 ──[10 Mbps]── s2 ── h2 (10.0.0.2)
    h3 (10.0.0.3) ──┘

ONOS REST: {onos.base}
Live logs: tail -f /tmp/iperf_<tag>.log
    """)

    # Wait for ONOS to see both switches
    onos.wait_for_devices(expected=2, timeout=40)

    # Sanity-check connectivity (ONOS fwd will install flows on first ping)
    info("*** Testing connectivity (first ping triggers ONOS flow installation)\n")
    net.pingAll()

    start_iperf_server(h2)

    # ── Phase 1 ──────────────────────────────────────────────────────────────
    input("\n[ Press ENTER ] ▶  PHASE 1: h1->h2 at 8 Mbps (no contention)")
    print()
    run_iperf_client(h1, h2.IP(), bandwidth_mbps=8, port=H1_PORT, duration=600, tag="h1")
    print("  h1->h2 iperf3 started at 8 Mbps.")
    print("  Watch:  tail -f /tmp/iperf_h1.log")
    print("  Expect: ~8 Mbps  ✅")

    # ── Phase 2 ──────────────────────────────────────────────────────────────
    input("\n[ Press ENTER ] ▶  PHASE 2: h3 surges at 10 Mbps (contention!)")
    print()
    run_iperf_client(h3, h2.IP(), bandwidth_mbps=8,  port=H3_PORT, duration=600, tag="h3")
    print("  h3->h2 surge started at 10 Mbps.")
    print("  Watch:  tail -f /tmp/iperf_h1.log  ← h1 throughput will DROP")
    print("          tail -f /tmp/iperf_h3.log")
    print("  Expect: both flows get ~5 Mbps each (fair share of 10 Mbps)  📉")

    # ── Phase 3 ──────────────────────────────────────────────────────────────
    input("\n[ Press ENTER ] ▶  PHASE 3: Apply OVS queues (streams will restart)")
    print()

    # Stop existing flows — ONOS fwd has already installed exact-match flow entries
    # for the live TCP connections with plain output actions (no queue). Those stale
    # entries would bypass the queue rule. Restarting forces fresh connections that
    # hit the queue rule before fwd can reinstall a stale one.
    info("*** Stopping iperf3 clients and servers\n")
    h1.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
    h3.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
    h2.cmd("pkill -f iperf3 2>/dev/null; true")
    time.sleep(1)
    # Restart servers before installing rules so they are ready for new connections
    start_iperf_server(h2)

    # 1. Provision OVS queues on s1's bottleneck port
    iface, ofport = setup_ovs_queues(s1)

    # 2. Find the h1-facing port on s1 (so we can match in_port in the flow)
    h1_iface  = get_iface_facing(s1, "h1")
    h1_ofport = get_ofport(s1, h1_iface)

    # 3. Push queue rule via ONOS REST API.
    #    ONOS owns the rule (appId=org.onosproject.cli) so it will never evict it.
    #    Priority=40000 beats fwd's priority=10 cleanly.
    #    Match: IN_PORT (h1 port) + ETH_SRC (h1 MAC) — same L2 fields fwd uses.
    #    Action: QUEUE(1) then OUTPUT — queue instruction must come before output.
    h1_mac = h1.MAC()
    s1_dev_id = f"of:{int(s1.dpid):016x}"
    info(f"\n*** Pushing queue flow rule via ONOS REST\n")
    info(f"    Device : {s1_dev_id}\n")
    info(f"    Match  : IN_PORT={h1_ofport}, ETH_SRC={h1_mac}\n")
    info(f"    Action : QUEUE(1), OUTPUT({ofport})\n")

    flow = {
        "priority": 40000,
        "timeout": 0,
        "isPermanent": True,
        "appId": "org.onosproject.cli",
        "treatment": {
            "instructions": [
                {"type": "QUEUE", "queueId": 1},
                {"type": "OUTPUT", "port": str(ofport)}
            ]
        },
        "selector": {
            "criteria": [
                {"type": "IN_PORT", "port": str(h1_ofport)},
                {"type": "ETH_SRC", "mac":  h1_mac},
            ]
        }
    }
    try:
        resp = onos.post(f"/flows/{s1_dev_id}", flow)
        info(f"    ✓ Rule pushed (HTTP {resp.status_code})\n")
    except requests.exceptions.HTTPError as e:
        info(f"    ✗ ONOS REST push failed: {e}\n")
        info(f"      Response body: {e.response.text}\n")
        info( "      Falling back to ovs-ofctl\n")
        s1.cmd(
            f'ovs-ofctl -O OpenFlow13 add-flow s1 '
            f'priority=40000,in_port={h1_ofport},dl_src={h1_mac},'
            f'actions=set_queue:1,output:{ofport}'
        )


    # 4. Restart both flows — new TCP connections will match the queue rule
    info("*** Restarting iperf3 clients\n")
    run_iperf_client(h1, h2.IP(), bandwidth_mbps=8, port=H1_PORT, duration=600, tag="h1")
    time.sleep(0.5)
    run_iperf_client(h3, h2.IP(), bandwidth_mbps=8, port=H3_PORT, duration=600, tag="h3")

    print(f"""
  QoS queues active on {iface} (s1→s2):
    Queue 1 → h1 traffic  : guaranteed 8 Mbps, max 8 Mbps
    Queue 0 → h3 traffic  : best-effort (~2 Mbps remainder)

  Watch:  tail -f /tmp/iperf_h1.log  ← should hold ~8 Mbps  ✅
          tail -f /tmp/iperf_h3.log  ← will get ~2 Mbps remainder

  ONOS UI: http://{onos_ip}:8181/onos/ui
    """)

    input("[ Press ENTER ] ▶  Open Mininet CLI (type 'exit' to finish)")
    CLI(net)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OVS Contention Demo with ONOS")
    parser.add_argument("--onos-ip",        default="172.17.0.2")
    parser.add_argument("--onos-rest-port", default=8181, type=int)
    parser.add_argument("--onos-user",      default="onos")
    parser.add_argument("--onos-pass",      default="rocks")
    parser.add_argument("--onos-of-port",   default=6653, type=int,
                        help="OpenFlow port ONOS listens on (default 6653)")
    args = parser.parse_args()

    setLogLevel("info")

    onos = ONOSClient(args.onos_ip, args.onos_rest_port,
                      args.onos_user, args.onos_pass)

    info("*** Checking ONOS connectivity\n")
    alive, err = onos.check_alive()
    if not alive:
        print(f"\n✗  Cannot reach ONOS REST API at {onos.base}")
        print(f"   Error: {err}")
        print( "")
        print( "   Troubleshooting:")
        print( "   1. Try the Docker container IP directly:")
        print( "      sudo python3 contention_demo_onos.py --onos-ip 172.17.0.2")
        print( "   2. Verify requests is installed for root:")
        print( "      sudo python3 -c \"import requests; print('ok')\"")
        print( "   3. Test manually:")
        print(f"      curl -u {args.onos_user}:{args.onos_pass} {onos.base}/devices\n")
        sys.exit(1)
    info(f"    ✓ ONOS REST API reachable at {onos.base}\n")

    net = Mininet(
        controller=None,    # we add RemoteController manually
        switch=OVSKernelSwitch,
        link=TCLink,
        autoSetMacs=False,  # we set MACs explicitly in build_topology
    )

    # Point all switches at ONOS
    net.addController(
        "onos",
        controller=RemoteController,
        ip=args.onos_ip,
        port=args.onos_of_port,
    )

    h1, h2, h3, s1, s2 = build_topology(net)

    info("*** Starting network\n")
    net.start()

    try:
        interactive_demo(net, h1, h2, h3, s1, s2, onos, args.onos_ip)
    finally:
        info("\n*** Cleaning up\n")
        h1.cmd("pkill -f iperf3 2>/dev/null; true")
        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        h3.cmd("pkill -f iperf3 2>/dev/null; true")

        teardown_ovs_queues(s1)

        info("*** Stopping network\n")
        net.stop()


if __name__ == "__main__":
    main()