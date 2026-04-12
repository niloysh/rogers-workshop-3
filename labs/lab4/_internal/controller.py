#!/usr/bin/env python3
"""
slice_controller.py
───────────────────
Transport Slice Controller — Lab 4 (ONOS edition)

Controller used in Lab 4 with ONOS-controlled switches:

  - Queue flow rules are installed via the ONOS REST API so ONOS tracks them
    as its own rules and will not evict them during flow reconciliation
  - SRv6 setup uses on-link routes instead of static neighbours; ONOS handles
    neighbour discovery via reactive forwarding with ipv6Forwarding=true
  - Provisioning an SRv6 slice installs both the forward route and the
    matching reverse route automatically
  - r1 (dual-homed SRv6 router) has two SIDs: fc00::a1 on eth0 (s1-facing)
    and fc00::a2 on eth1 (s2-facing); configure_srv6() handles it specially
  - h3 is on s1, so r1's routing table includes fc00::3 via eth0

API used in this lab:
    sc = SliceController(net, ingress=s1, peer=s2, link_bw=10)
    sc.configure_srv6("h1", "h2", "h3", "mb1", "mb2", "r1")
    sc.provision("premium", src="h1", dst="h2", chain=["r1", "mb1"], bw=8)
    sc.teardown("premium")
    sc.status()
"""

import time
from pathlib import Path
import requests


# ─── Exceptions ───────────────────────────────────────────────────────────────

class AdmissionError(Exception):
    """Raised when a slice request exceeds available bandwidth."""
    pass


class SliceError(Exception):
    """Raised for invalid slice operations."""
    pass


# ─── SRv6 SID table ───────────────────────────────────────────────────────────

SID = {
    "h1":  "fc00::1",
    "h2":  "fc00::2",
    "h3":  "fc00::3",
    "mb1": "fc00::b1",
    "mb2": "fc00::b2",
    "r1":  "fc00::a1",   # eth0, s1-facing — use in forward chain
    "r1b": "fc00::a2",   # eth1, s2-facing — use in reverse chain
}

SID_SUBNET = "fc00::/64"

ONOS_REST_URL = "http://127.0.0.1:8181/onos/v1"
ONOS_AUTH     = ("onos", "rocks")

MB1_LOG = "/tmp/mb1_bandwidth.log"
MB2_LOG = "/tmp/mb2_security.log"
MIDDLEBOX_DIR = Path(__file__).resolve().parent / "middleboxes"
MB1_SCRIPT = MIDDLEBOX_DIR / "mb1_telemetry.py"
MB2_SCRIPT = MIDDLEBOX_DIR / "mb2_security.py"


# ─── SliceController ──────────────────────────────────────────────────────────

class SliceController:
    """
    Manages transport slices on a two-switch Mininet topology under ONOS.

    Parameters
    ----------
    net      : Mininet    The running Mininet network object.
    ingress  : OVSSwitch  Ingress switch (h1, h3, r1 connect here via s1).
    peer     : OVSSwitch  Switch on the other end of the bottleneck (s2).
    link_bw  : int        Bottleneck link capacity in Mbps (default 10).
    """

    def __init__(self, net, ingress, peer, link_bw=10):
        self.net            = net
        self.ingress        = ingress
        self.peer           = peer
        self.link_bw        = link_bw
        self._slices        = {}
        self._next_queue_id = 1

        self._iface, self._bottleneck_ofport = self._init_qos()

    # ── Public API ────────────────────────────────────────────────────────────

    def provision(self, name, src, dst, chain=None, bw=0):
        """
        Provision a transport slice.

        Parameters
        ----------
        name  : str   Unique slice name
        src   : str   Source host name (e.g. "h1")
        dst   : str   Destination host name (e.g. "h2")
        chain : list  Ordered waypoint names (e.g. ["r1", "mb1"])
                      Use "r1" for the s1-facing SID, "r1b" for s2-facing.
        bw    : float Guaranteed bandwidth in Mbps on s1-s2 (0 = best-effort)

        Notes
        -----
        If chain is non-empty, the controller installs:
          - a forward SRv6 route on src toward dst
          - a reverse SRv6 route on dst toward src
        The reverse chain is derived automatically by reversing the forward
        chain and swapping r1 <-> r1b where needed.

        Raises
        ------
        SliceError      if name already exists or hosts are invalid
        AdmissionError  if requested bandwidth exceeds available capacity
        """
        if chain is None:
            chain = []

        if name in self._slices:
            raise SliceError(f"Slice '{name}' already exists")
        self._validate_hosts(src, dst, chain)

        if bw > 0:
            self._check_admission(name, bw)

        print(f"\n[SliceController] Provisioning slice '{name}'")
        print(f"  src={src}  dst={dst}  chain={chain or 'direct'}  bw={bw} Mbps")

        src_host = self.net.get(src)
        dst_host = self.net.get(dst)

        queue_id = None
        flow_id  = None
        if bw > 0:
            queue_id = self._next_queue_id
            self._next_queue_id += 1
            self._add_queue(queue_id, bw)
            flow_id = self._add_queue_flow(src_host, queue_id)
            print(f"  [queue]  queue_id={queue_id}, {bw} Mbps guaranteed")

        segments = []
        reverse_chain = []
        reverse_segments = []
        if chain:
            segments = self._build_segments(chain, dst)
            self._install_srv6_route(src_host, dst_host.IP(), segments)
            reverse_chain = self._build_reverse_chain(chain)
            reverse_segments = self._build_segments(reverse_chain, src)
            self._install_srv6_route(dst_host, src_host.IP(), reverse_segments)
            print(f"  [SRv6]   forward: {src} → {' → '.join(chain)} → {dst}")
            print(f"  [SRv6]   fwd segs: {' → '.join(segments)}")
            print(f"  [SRv6]   reverse: {dst} → {' → '.join(reverse_chain)} → {src}")
            print(f"  [SRv6]   rev segs: {' → '.join(reverse_segments)}")

        for waypoint in chain:
            self._start_logger(waypoint)

        self._slices[name] = {
            "src":      src,
            "dst":      dst,
            "chain":    chain,
            "bw":       bw,
            "queue_id": queue_id,
            "flow_id":  flow_id,
            "segments": segments,
            "reverse_chain": reverse_chain,
            "reverse_segments": reverse_segments,
        }

        print(f"[SliceController] Slice '{name}' provisioned ✓\n")

    def teardown(self, name):
        """Remove a transport slice and restore best-effort for its traffic."""
        if name not in self._slices:
            raise SliceError(f"Slice '{name}' not found")

        s = self._slices[name]
        print(f"\n[SliceController] Tearing down slice '{name}'")

        src_host = self.net.get(s["src"])
        dst_host = self.net.get(s["dst"])

        if s["segments"]:
            self._remove_srv6_route(src_host, dst_host.IP())
            self._remove_srv6_route(dst_host, src_host.IP())
            print(f"  [SRv6]   routes removed from {s['src']} and {s['dst']}")

        if s["queue_id"] is not None:
            self._remove_queue_flow(s["flow_id"])
            self._remove_queue(s["queue_id"])
            print(f"  [queue]  queue {s['queue_id']} removed")

        for waypoint in s["chain"]:
            self._stop_logger(waypoint)

        del self._slices[name]
        print(f"[SliceController] Slice '{name}' torn down ✓\n")

    def status(self):
        """Print a summary of all active slices and bandwidth usage."""
        reserved  = sum(s["bw"] for s in self._slices.values())
        available = self.link_bw - reserved

        print(f"\n[SliceController] Status")
        print(f"  Link capacity : {self.link_bw} Mbps")
        print(f"  Reserved      : {reserved} Mbps")
        print(f"  Available     : {available} Mbps")
        print(f"  Active slices : {len(self._slices)}")

        if not self._slices:
            print("  (none)")
        else:
            print()
            for name, s in self._slices.items():
                chain_str = " → ".join(s["chain"]) if s["chain"] else "direct"
                bw_str    = f"{s['bw']} Mbps" if s["bw"] > 0 else "best-effort"
                print(f"  [{name}]")
                print(f"    path:      {s['src']} → {chain_str} → {s['dst']}")
                if s["reverse_chain"]:
                    reverse_chain_str = " → ".join(s["reverse_chain"])
                    print(f"    reverse:   {s['dst']} → {reverse_chain_str} → {s['src']}")
                print(f"    bandwidth: {bw_str}")
                if s["queue_id"]:
                    print(f"    queue_id:  {s['queue_id']}")
                if s["segments"]:
                    print(f"    fwd segs:  {' → '.join(s['segments'])}")
                if s["reverse_segments"]:
                    print(f"    rev segs:  {' → '.join(s['reverse_segments'])}")
        print()

    def teardown_all(self):
        """Remove all active slices."""
        for name in list(self._slices.keys()):
            self.teardown(name)

    # ── SRv6 setup ────────────────────────────────────────────────────────────

    def configure_srv6(self, *names):
        """
        Enable SRv6 on hosts and r1, assign SIDs, and install on-link routes.

        Unlike Lab 4, this does NOT install static neighbour entries.
        ONOS's reactive forwarding (with ipv6Forwarding=true) handles
        neighbour discovery dynamically once pingAll() has populated the
        MAC table.

        Call once after net.start(). Run pingAll() afterwards.
        """
        print("\n[SliceController] Configuring SRv6")

        for name in names:
            if name == "r1":
                self._configure_r1()
            else:
                node = self.net.get(name)
                self._configure_srv6_host(node, SID[name])

        time.sleep(2)
        print("[SliceController] SRv6 configured ✓\n")

    def verify_srv6(self, src_name, *dst_names):
        """Ping6 each dst SID from src and report reachability."""
        src = self.net.get(src_name)
        print(f"\n[SliceController] Verifying SRv6 reachability from {src_name}")
        all_ok = True
        for name in dst_names:
            sid = SID[name]
            rc  = src.cmd(
                f"ping6 -c 1 -W 2 {sid} > /dev/null 2>&1; echo $?"
            ).strip()
            ok  = rc == "0"
            print(f"  {src_name} → {name} ({sid}): {'✓' if ok else '✗'}")
            all_ok = all_ok and ok
        print()
        return all_ok

    def warmup_ndp(self, *names):
        """
        Fire one-shot ping6s between all listed hosts to populate NDP caches.

        Call after pingAll() and configure_srv6(). Skips r1/r1b (they are
        routers, not hosts with fc00:: SIDs reachable via ONOS reactive fwd).
        """
        host_names = [n for n in names if n not in ("r1", "r1b") and n in SID]
        print(f"\n[SliceController] Warming up NDP between {len(host_names)} hosts")
        for src_name in host_names:
            src = self.net.get(src_name)
            for dst_name in host_names:
                if dst_name != src_name:
                    src.cmd(
                        f"ping6 -c 1 -W 1 {SID[dst_name]} > /dev/null 2>&1 &"
                    )
        time.sleep(2)
        print("[SliceController] NDP warmup complete\n")

    # ── Internal: QoS initialisation ─────────────────────────────────────────

    def _init_qos(self):
        iface = self._get_iface_facing(self.ingress, self.peer.name)

        self.ingress.cmd(f"ovs-vsctl clear port {iface} qos")
        self.ingress.cmd("ovs-vsctl --all destroy qos   2>/dev/null; true")
        self.ingress.cmd("ovs-vsctl --all destroy queue 2>/dev/null; true")

        self.ingress.cmd(
            f'ovs-vsctl set port {iface} qos=@newqos -- '
            f'--id=@newqos create qos type=linux-htb '
            f'other-config:max-rate={self.link_bw * 1_000_000} '
            f'queues:0=@q0 -- '
            f'--id=@q0 create queue '
            f'other-config:min-rate=1000000 '
            f'other-config:max-rate={self.link_bw * 1_000_000} '
            f'other-config:burst=125000'
        )

        ofport = self._get_ofport(self.ingress, iface)
        return iface, ofport

    # ── Internal: queue management ────────────────────────────────────────────

    def _add_queue(self, queue_id, bw_mbps):
        bw_bps   = int(bw_mbps * 1_000_000)
        burst    = 15000
        qos_uuid = self.ingress.cmd(
            f"ovs-vsctl get port {self._iface} qos"
        ).strip()
        self.ingress.cmd(
            f'ovs-vsctl -- --id=@q create queue '
            f'other-config:min-rate={bw_bps} '
            f'other-config:max-rate={bw_bps} '
            f'other-config:burst={burst} '
            f'-- set qos {qos_uuid} queues:{queue_id}=@q'
        )
        htb_class = f"1:{queue_id + 1}"
        self.ingress.cmd(
            f"tc qdisc add dev {self._iface} parent {htb_class} "
            f"handle {queue_id + 1}0: fq_codel limit 50 target 5ms interval 100ms "
            f"2>/dev/null; true"
        )

    def _add_queue_flow(self, src_host, queue_id):
        """
        Install the queue steering flow via the ONOS REST API.

        Installing via ovs-ofctl adds a flow that ONOS does not track —
        ONOS evicts it during flow reconciliation. Installing via REST
        makes ONOS the owner of the rule so it persists until explicitly
        deleted through the same API.

        Returns the ONOS flow ID string needed for later deletion.
        """
        h1_iface    = self._get_iface_facing(self.ingress, src_host.name)
        h1_ofport   = int(self._get_ofport(self.ingress, h1_iface))
        peer_iface  = self._get_iface_facing(self.ingress, self.peer.name)
        peer_ofport = int(self._get_ofport(self.ingress, peer_iface))
        device_id   = self._get_device_id(self.ingress)

        flow = {
            "priority": 100,
            "isPermanent": True,
            "deviceId": device_id,
            "selector": {
                "criteria": [
                    {"type": "IN_PORT", "port": h1_ofport},
                    {"type": "ETH_SRC", "mac": src_host.MAC()},
                ]
            },
            "treatment": {
                "instructions": [
                    {"type": "QUEUE", "queueId": queue_id},
                    {"type": "OUTPUT", "port": peer_ofport},
                ]
            },
        }

        resp = requests.post(
            f"{ONOS_REST_URL}/flows",
            json={"flows": [flow]},
            auth=ONOS_AUTH,
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()["flows"][0]["flowId"]

    def _remove_queue_flow(self, flow_id):
        """Delete the queue steering flow from ONOS by its flow ID."""
        device_id = self._get_device_id(self.ingress)
        requests.delete(
            f"{ONOS_REST_URL}/flows/{device_id}/{flow_id}",
            auth=ONOS_AUTH,
            timeout=5,
        )

    def _remove_queue(self, queue_id):
        qos_uuid = self.ingress.cmd(
            f"ovs-vsctl get port {self._iface} qos"
        ).strip()
        self.ingress.cmd(
            f"ovs-vsctl remove qos {qos_uuid} queues {queue_id} 2>/dev/null; true"
        )
        self._restore_tc_shaper(self._iface, self.link_bw)

    def _restore_tc_shaper(self, iface, bw_mbps):
        bw_kbps  = bw_mbps * 1000
        burst_kb = bw_mbps * 2
        self.ingress.cmd(f"tc qdisc del dev {iface} root 2>/dev/null; true")
        self.ingress.cmd(
            f"tc qdisc add dev {iface} root handle 1: htb default 10 && "
            f"tc class add dev {iface} parent 1: classid 1:10 htb "
            f"rate {bw_kbps}kbit burst {burst_kb}kb"
        )

    # ── Internal: SRv6 ───────────────────────────────────────────────────────

    def _configure_srv6_host(self, host, sid):
        iface = f"{host.name}-eth0"
        host.cmd("sysctl -w net.ipv6.conf.all.forwarding=1   > /dev/null")
        host.cmd("sysctl -w net.ipv6.conf.all.seg6_enabled=1 > /dev/null")
        host.cmd(f"sysctl -w net.ipv6.conf.{iface}.seg6_enabled=1 > /dev/null")
        host.cmd(f"ip -6 addr add {sid}/128 dev {iface} 2>/dev/null; true")
        host.cmd(f"ip -6 route replace {SID_SUBNET} dev {iface} 2>/dev/null; true")
        print(f"  {host.name}: SID={sid}")

    def _configure_r1(self):
        """
        Configure r1 as a dual-homed SRv6 router.

        r1-eth0 faces s1 (h1 fc00::1, h3 fc00::3 live here)
        r1-eth1 faces s2 (h2, mb1, mb2 live here)

        Routes on r1:
          fc00::/64    dev r1-eth1   (default: toward s2)
          fc00::1/128  dev r1-eth0   (h1 is on s1)
          fc00::3/128  dev r1-eth0   (h3 is on s1)

        SIDs:
          fc00::a1 on r1-eth0 — forward chain ingress (h1 → r1 via s1)
          fc00::a2 on r1-eth1 — reverse chain ingress (mb1 → r1 via s2)
        """
        r1 = self.net.get("r1")
        r1.cmd("sysctl -w net.ipv6.conf.all.forwarding=1   > /dev/null")
        r1.cmd("sysctl -w net.ipv6.conf.all.seg6_enabled=1 > /dev/null")
        for iface in ["r1-eth0", "r1-eth1"]:
            r1.cmd(f"sysctl -w net.ipv6.conf.{iface}.seg6_enabled=1 > /dev/null")

        # Specific routes — not ECMP
        r1.cmd("ip -6 route replace fc00::/64   dev r1-eth1 2>/dev/null; true")
        r1.cmd("ip -6 route replace fc00::1/128 dev r1-eth0 2>/dev/null; true")
        r1.cmd("ip -6 route replace fc00::3/128 dev r1-eth0 2>/dev/null; true")

        # Assign SIDs
        r1.cmd(f"ip -6 addr add {SID['r1']}/128  dev r1-eth0 2>/dev/null; true")
        r1.cmd(f"ip -6 addr add {SID['r1b']}/128 dev r1-eth1 2>/dev/null; true")

        print(f"  r1: SID={SID['r1']} (eth0) / {SID['r1b']} (eth1)")

    def _build_segments(self, chain, dst):
        return [SID[wp] for wp in chain] + [SID[dst]]

    def _build_reverse_chain(self, chain):
        reverse_map = {
            "r1": "r1b",
            "r1b": "r1",
        }
        return [reverse_map.get(waypoint, waypoint) for waypoint in reversed(chain)]

    def _install_srv6_route(self, src_host, dst_ip, segments):
        segs = ",".join(segments)
        src_host.cmd(
            f"ip route replace {dst_ip} "
            f"encap seg6 mode encap segs {segs} dev {src_host.name}-eth0"
        )

    def _remove_srv6_route(self, src_host, dst_ip):
        src_host.cmd(f"ip route del {dst_ip} 2>/dev/null; true")

    # ── Internal: waypoint loggers ────────────────────────────────────────────

    def _start_logger(self, waypoint):
        if waypoint in ("r1", "r1b"):
            return
        host = self.net.get(waypoint)
        if waypoint == "mb1":
            self._start_mb1_logger(host)
        elif waypoint == "mb2":
            self._start_mb2_logger(host)

    def _stop_logger(self, waypoint):
        if waypoint in ("r1", "r1b"):
            return
        host = self.net.get(waypoint)
        if waypoint == "mb1":
            host.cmd("pkill -f mb1_telemetry.py 2>/dev/null; true")
        elif waypoint == "mb2":
            host.cmd("pkill -f mb2_security.py 2>/dev/null; true")

    def _start_mb1_logger(self, mb1):
        """Telemetry monitor: counts SRv6 traffic delivered to mb1."""
        mb1.cmd("pkill -f mb1_telemetry.py 2>/dev/null; true")
        mb1.cmd(
            f"python3 {MB1_SCRIPT} "
            f"--iface mb1-eth0 --log {MB1_LOG} --dst-mac {mb1.MAC()} "
            f"> /tmp/mb1_logger_out.log 2>&1 &"
        )
        time.sleep(0.3)

    def _start_mb2_logger(self, mb2):
        """Security inspector: reports inspected SRv6 inner flows at mb2."""
        mb2.cmd("pkill -f mb2_security.py 2>/dev/null; true")
        mb2.cmd(
            f"python3 {MB2_SCRIPT} "
            f"--iface mb2-eth0 --log {MB2_LOG} --dst-mac {mb2.MAC()} "
            f"> /tmp/mb2_logger_out.log 2>&1 &"
        )
        time.sleep(0.3)

    # ── Internal: admission control ───────────────────────────────────────────

    def _check_admission(self, name, bw):
        reserved  = sum(s["bw"] for s in self._slices.values())
        available = self.link_bw - reserved
        if bw > available:
            slices_summary = "\n".join(
                f"    {n}: {s['bw']} Mbps"
                for n, s in self._slices.items()
                if s["bw"] > 0
            ) or "    (none)"
            raise AdmissionError(
                f"\n[AdmissionError] Cannot provision slice '{name}'\n"
                f"  Requested : {bw} Mbps\n"
                f"  Available : {available} Mbps\n"
                f"  Reserved  : {reserved} Mbps\n"
                f"  Capacity  : {self.link_bw} Mbps\n"
                f"  Active slices:\n{slices_summary}\n"
                f"\n  Hint: reduce bandwidth, or teardown an existing slice first."
            )

    def _validate_hosts(self, src, dst, chain):
        for name in [src, dst] + chain:
            if name not in ("r1b",) and self.net.get(name) is None:
                raise SliceError(f"Host '{name}' not found in topology")
            if name not in SID and chain and name in chain:
                raise SliceError(f"No SID configured for waypoint '{name}'")

    # ── Internal: OVS helpers ─────────────────────────────────────────────────

    def _get_device_id(self, switch):
        """Return the ONOS device ID for an OVS switch (e.g. 'of:0000000000000001')."""
        dpid = switch.cmd(
            f"ovs-vsctl get bridge {switch.name} datapath-id"
        ).strip().strip('"')
        return f"of:{dpid}"

    def _get_iface_facing(self, switch, peer_name):
        for intf in switch.intfList():
            if intf.link:
                other = (intf.link.intf2 if intf.link.intf1 == intf
                         else intf.link.intf1)
                if other.node.name == peer_name:
                    return intf.name
        raise RuntimeError(f"No link between {switch.name} and {peer_name}")

    def _get_ofport(self, switch, iface):
        return switch.cmd(
            f"ovs-vsctl get Interface {iface} ofport"
        ).strip()
