#!/usr/bin/env python3
"""
slice_controller.py
───────────────────
Transport Slice Controller

Provides a clean API for provisioning and tearing down transport slices
on a Mininet topology with standalone OVS switches.

A transport slice is a contract with two components:
  - Path contract:      SRv6 forces traffic through a defined chain of waypoints
  - Bandwidth contract: OVS HTB queue guarantees a minimum rate on the bottleneck

API:
    sc = SliceController(net, s1, s2)
    sc.provision("premium", src="h1", dst="h2", chain=["mb1"], bw=8)
    sc.teardown("premium")
    sc.status()

Admission control:
    The controller tracks total reserved bandwidth on the bottleneck link.
    provision() raises AdmissionError if the requested bandwidth would
    exceed available capacity.
"""

import time


# ─── Exceptions ───────────────────────────────────────────────────────────────

class AdmissionError(Exception):
    """Raised when a slice request exceeds available bandwidth."""
    pass


class SliceError(Exception):
    """Raised for invalid slice operations."""
    pass


# ─── SRv6 SID table ───────────────────────────────────────────────────────────
# Maps host names to their IPv6 Segment IDs.
# Add entries here when new hosts are added to the topology.

SID = {
    "h1":  "fc00::1",
    "h2":  "fc00::2",
    "h3":  "fc00::3",
    "mb1": "fc00::b1",
    "mb2": "fc00::b2",
}

SID_SUBNET = "fc00::/64"

MB1_LOG = "/tmp/mb1_bandwidth.log"
MB2_LOG = "/tmp/mb2_packets.log"


# ─── SliceController ──────────────────────────────────────────────────────────

class SliceController:
    """
    Manages transport slices on a two-switch Mininet topology.

    Parameters
    ----------
    net : Mininet
        The running Mininet network object.
    s1 : OVSSwitch
        Ingress switch (where h1 and h3 connect).
    s2 : OVSSwitch
        Egress switch (where h2, mb1, mb2 connect).
    link_bw : int
        Bottleneck link capacity in Mbps (default 10).
    """

    def __init__(self, net, s1, s2, link_bw=10):
        self.net      = net
        self.s1       = s1
        self.s2       = s2
        self.link_bw  = link_bw
        self._slices  = {}          # name → slice state dict
        self._next_queue_id = 1     # queue 0 is best-effort, start at 1

        # Set up base QoS on s1→s2 bottleneck (best-effort queue 0 only)
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
        chain : list  Ordered list of waypoint host names (e.g. ["mb1"])
                      Empty list means direct path, no SRv6 steering.
        bw    : float Guaranteed bandwidth in Mbps (0 = best-effort)

        Raises
        ------
        SliceError      if name already exists or hosts are invalid
        AdmissionError  if requested bandwidth exceeds available capacity
        """
        if chain is None:
            chain = []

        # Validate
        if name in self._slices:
            raise SliceError(f"Slice '{name}' already exists")
        self._validate_hosts(src, dst, chain)

        # Admission control
        if bw > 0:
            self._check_admission(name, bw)

        print(f"\n[SliceController] Provisioning slice '{name}'")
        print(f"  src={src}  dst={dst}  chain={chain or 'direct'}  bw={bw} Mbps")

        src_host = self.net.get(src)
        dst_host = self.net.get(dst)

        # 1. Bandwidth: allocate OVS queue if bw > 0
        queue_id = None
        if bw > 0:
            queue_id = self._next_queue_id
            self._next_queue_id += 1
            self._add_queue(queue_id, bw)
            self._add_queue_flow(src_host, queue_id)
            print(f"  [queue]  queue_id={queue_id}, {bw} Mbps guaranteed")

        # 2. Path: install SRv6 route if chain is non-empty
        segments = []
        if chain:
            segments = self._build_segments(chain, dst)
            self._install_srv6_route(src_host, dst_host.IP(), segments)
            print(f"  [SRv6]   {src} → {' → '.join(chain)} → {dst}")
            print(f"  [SRv6]   segments: {' → '.join(segments)}")

        # 3. Start waypoint loggers
        for waypoint in chain:
            self._start_logger(waypoint)

        # Persist slice state
        self._slices[name] = {
            "src":       src,
            "dst":       dst,
            "chain":     chain,
            "bw":        bw,
            "queue_id":  queue_id,
            "segments":  segments,
        }

        print(f"[SliceController] Slice '{name}' provisioned ✓\n")

    def teardown(self, name):
        """
        Remove a transport slice and restore best-effort for its traffic.

        Parameters
        ----------
        name : str  Name of the slice to remove

        Raises
        ------
        SliceError  if the slice does not exist
        """
        if name not in self._slices:
            raise SliceError(f"Slice '{name}' not found")

        s = self._slices[name]
        print(f"\n[SliceController] Tearing down slice '{name}'")

        src_host = self.net.get(s["src"])
        dst_host = self.net.get(s["dst"])

        # Remove SRv6 route
        if s["segments"]:
            self._remove_srv6_route(src_host, dst_host.IP())
            print(f"  [SRv6]   route removed from {s['src']}")

        # Remove queue and flow rule
        if s["queue_id"] is not None:
            self._remove_queue_flow(src_host)
            self._remove_queue(s["queue_id"])
            print(f"  [queue]  queue {s['queue_id']} removed")

        # Stop waypoint loggers
        for waypoint in s["chain"]:
            self._stop_logger(waypoint)

        del self._slices[name]
        print(f"[SliceController] Slice '{name}' torn down ✓\n")

    def status(self):
        """Print a summary of all active slices and bandwidth usage."""
        reserved = sum(s["bw"] for s in self._slices.values())
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
                print(f"    bandwidth: {bw_str}")
                if s["queue_id"]:
                    print(f"    queue_id:  {s['queue_id']}")
                if s["segments"]:
                    print(f"    segments:  {' → '.join(s['segments'])}")
        print()

    def teardown_all(self):
        """Remove all active slices. Used for cleanup."""
        for name in list(self._slices.keys()):
            self.teardown(name)

    # ── SRv6 setup (called once at startup) ──────────────────────────────────

    def configure_srv6(self, *host_names):
        """
        Enable SRv6 on the given hosts, assign SIDs, and install static
        IPv6 neighbour entries so forwarding works without NDP.

        Call this once after net.start() before provisioning any slices.

        Parameters
        ----------
        *host_names : str  Host names to configure (e.g. "h1", "h2", "mb1")
        """
        print("\n[SliceController] Configuring SRv6")

        # Build neighbour table for all hosts being configured
        all_info = {}
        for name in host_names:
            host = self.net.get(name)
            all_info[name] = (SID[name], host.MAC())

        for name in host_names:
            host = self.net.get(name)
            self._configure_srv6_host(host, SID[name], all_info)

        # Wait for DAD (Duplicate Address Detection)
        time.sleep(2)
        print("[SliceController] SRv6 configured ✓\n")

    def verify_srv6(self, src_name, *dst_names):
        """
        Ping6 each dst SID from src and report reachability.
        Returns True if all destinations are reachable.
        """
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

    # ── Internal: QoS initialisation ─────────────────────────────────────────

    def _init_qos(self):
        """
        Set up the base HTB QoS on s1→s2 with queue 0 (best-effort only).
        Called once at construction time.
        """
        iface = self._get_iface_facing(self.s1, "s2")

        # Clean slate
        self.s1.cmd(f"ovs-vsctl clear port {iface} qos")
        self.s1.cmd("ovs-vsctl --all destroy qos   2>/dev/null; true")
        self.s1.cmd("ovs-vsctl --all destroy queue 2>/dev/null; true")

        # Create root QoS with best-effort queue 0 only
        self.s1.cmd(
            f'ovs-vsctl set port {iface} qos=@newqos -- '
            f'--id=@newqos create qos type=linux-htb '
            f'other-config:max-rate={self.link_bw * 1_000_000} '
            f'queues:0=@q0 -- '
            f'--id=@q0 create queue '
            f'other-config:min-rate=1000000 '
            f'other-config:max-rate={self.link_bw * 1_000_000} '
            f'other-config:burst=125000'
        )

        ofport = self._get_ofport(self.s1, iface)
        return iface, ofport

    # ── Internal: queue management ────────────────────────────────────────────

    def _add_queue(self, queue_id, bw_mbps):
        """Add a new HTB queue to the existing QoS on the bottleneck port."""
        bw_bps   = int(bw_mbps * 1_000_000)
        burst    = 62500   # 62 KB — keeps TCP cwnd in check
        qos_uuid = self.s1.cmd(
            f"ovs-vsctl get port {self._iface} qos"
        ).strip()
        self.s1.cmd(
            f'ovs-vsctl -- --id=@q create queue '
            f'other-config:min-rate={bw_bps} '
            f'other-config:max-rate={bw_bps} '
            f'other-config:burst={burst} '
            f'-- set qos {qos_uuid} queues:{queue_id}=@q'
        )

    def _add_queue_flow(self, src_host, queue_id):
        """Install ovs-ofctl flow to steer src_host traffic into queue_id."""
        h1_iface  = self._get_iface_facing(self.s1, src_host.name)
        h1_ofport = self._get_ofport(self.s1, h1_iface)
        self.s1.cmd(
            f'ovs-ofctl add-flow s1 '
            f'priority=100,'
            f'in_port={h1_ofport},'
            f'dl_src={src_host.MAC()},'
            f'actions=set_queue:{queue_id},normal'
        )

    def _remove_queue_flow(self, src_host):
        """Remove the queue steering flow for src_host."""
        h1_iface  = self._get_iface_facing(self.s1, src_host.name)
        h1_ofport = self._get_ofport(self.s1, h1_iface)
        self.s1.cmd(
            f"ovs-ofctl del-flows s1 "
            f"priority=100,in_port={h1_ofport},dl_src={src_host.MAC()} "
            f"2>/dev/null; true"
        )

    def _remove_queue(self, queue_id):
        """Remove a queue from the QoS config and restore the TC shaper."""
        qos_uuid = self.s1.cmd(
            f"ovs-vsctl get port {self._iface} qos"
        ).strip()
        self.s1.cmd(
            f"ovs-vsctl remove qos {qos_uuid} queues {queue_id} 2>/dev/null; true"
        )
        # Restore TC shaper — OVS qos operations can disturb Mininet's TCLink qdiscs
        self._restore_tc_shaper(self._iface, self.link_bw)

    def _restore_tc_shaper(self, iface, bw_mbps):
        """Re-apply a simple HTB shaper after OVS QoS operations."""
        bw_kbps  = bw_mbps * 1000
        burst_kb = bw_mbps * 2
        self.s1.cmd(f"tc qdisc del dev {iface} root 2>/dev/null; true")
        self.s1.cmd(
            f"tc qdisc add dev {iface} root handle 1: htb default 10 && "
            f"tc class add dev {iface} parent 1: classid 1:10 htb "
            f"rate {bw_kbps}kbit burst {burst_kb}kb"
        )

    # ── Internal: SRv6 ───────────────────────────────────────────────────────

    def _configure_srv6_host(self, host, sid, all_info):
        iface = f"{host.name}-eth0"
        host.cmd("sysctl -w net.ipv6.conf.all.forwarding=1    > /dev/null")
        host.cmd("sysctl -w net.ipv6.conf.all.seg6_enabled=1  > /dev/null")
        host.cmd(f"sysctl -w net.ipv6.conf.{iface}.seg6_enabled=1 > /dev/null")
        host.cmd(f"ip -6 addr add {sid}/128 dev {iface} 2>/dev/null; true")
        host.cmd(f"ip -6 route add {SID_SUBNET} dev {iface} 2>/dev/null; true")
        for other_name, (other_sid, other_mac) in all_info.items():
            if other_name == host.name:
                continue
            host.cmd(
                f"ip -6 neigh replace {other_sid} lladdr {other_mac} "
                f"dev {iface} 2>/dev/null; true"
            )
        print(f"  {host.name}: SID={sid}")

    def _build_segments(self, chain, dst):
        """Build the SRv6 segment list for a given chain and destination."""
        return [SID[wp] for wp in chain] + [SID[dst]]

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
        host = self.net.get(waypoint)
        if waypoint == "mb1":
            self._start_mb1_logger(host)
        elif waypoint == "mb2":
            self._start_mb2_logger(host)

    def _stop_logger(self, waypoint):
        host = self.net.get(waypoint)
        host.cmd("pkill -f mb_logger 2>/dev/null; true")

    def _start_mb1_logger(self, mb1):
        """Bandwidth logger: counts bytes from h1's MAC, reports Mbps."""
        h1_mac = self.net.get("h1").MAC()
        script = "/tmp/mb1_logger.py"
        lines  = [
            "#!/usr/bin/env python3\n",
            "import socket, time, sys, signal\n",
            f'IFACE  = "mb1-eth0"\n',
            f'LOG    = "{MB1_LOG}"\n',
            f'H1_MAC = bytes.fromhex("{h1_mac.replace(":", "")}")\n',
            "ETH_P_ALL = 0x0003\n",
            "\n",
            "def loop():\n",
            "    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW,\n",
            "                         socket.htons(ETH_P_ALL))\n",
            "    sock.bind((IFACE, 0))\n",
            "    sock.settimeout(1.0)\n",
            '    open(LOG, "w").close()\n',
            "    while True:\n",
            "        total, deadline = 0, time.time() + 1.0\n",
            "        while time.time() < deadline:\n",
            "            try:\n",
            "                pkt = sock.recv(65535)\n",
            "                if pkt[6:12] == H1_MAC:\n",
            "                    total += len(pkt)\n",
            "            except socket.timeout:\n",
            "                break\n",
            "        mbps  = (total * 8) / 1_000_000\n",
            '        ts    = time.strftime("%H:%M:%S")\n',
            '        label = "  <- slice traffic" if mbps > 0.01 else ""\n',
            '        line  = f"[mb1] [{ts}]  {mbps:5.2f} Mbits/sec{label}\\n"\n',
            '        open(LOG, "a").write(line)\n',
            "        sys.stdout.write(line); sys.stdout.flush()\n",
            "\n",
            "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))\n",
            "loop()\n",
        ]
        with open(script, "w") as f:
            f.writelines(lines)
        mb1.cmd("pkill -f mb1_logger 2>/dev/null; true")
        mb1.cmd(f"python3 {script} > /tmp/mb1_logger_out.log 2>&1 &")
        time.sleep(0.3)

    def _start_mb2_logger(self, mb2):
        """Packet counter logger: counts packets per second at mb2."""
        script = "/tmp/mb2_logger.py"
        lines  = [
            "#!/usr/bin/env python3\n",
            "import socket, time, sys, signal\n",
            f'IFACE = "mb2-eth0"\n',
            f'LOG   = "{MB2_LOG}"\n',
            "ETH_P_ALL = 0x0003\n",
            "\n",
            "def loop():\n",
            "    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW,\n",
            "                         socket.htons(ETH_P_ALL))\n",
            "    sock.bind((IFACE, 0))\n",
            "    sock.settimeout(1.0)\n",
            '    open(LOG, "w").close()\n',
            "    while True:\n",
            "        pkts, deadline = 0, time.time() + 1.0\n",
            "        while time.time() < deadline:\n",
            "            try:\n",
            "                sock.recv(65535)\n",
            "                pkts += 1\n",
            "            except socket.timeout:\n",
            "                break\n",
            '        ts    = time.strftime("%H:%M:%S")\n',
            '        label = "  <- slice traffic" if pkts > 0 else ""\n',
            '        line  = f"[mb2] [{ts}]  {pkts:5d} pkts/sec{label}\\n"\n',
            '        open(LOG, "a").write(line)\n',
            "        sys.stdout.write(line); sys.stdout.flush()\n",
            "\n",
            "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))\n",
            "loop()\n",
        ]
        with open(script, "w") as f:
            f.writelines(lines)
        mb2.cmd("pkill -f mb2_logger 2>/dev/null; true")
        mb2.cmd(f"python3 {script} > /tmp/mb2_logger_out.log 2>&1 &")
        time.sleep(0.3)

    # ── Internal: admission control ───────────────────────────────────────────

    def _check_admission(self, name, bw):
        """
        Raise AdmissionError if bw Mbps cannot be accommodated.
        """
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
            if self.net.get(name) is None:
                raise SliceError(f"Host '{name}' not found in topology")
            if name not in SID and chain and name in chain:
                raise SliceError(f"No SID configured for waypoint '{name}'")

    # ── Internal: OVS helpers ─────────────────────────────────────────────────

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