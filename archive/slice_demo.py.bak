#!/usr/bin/env python3
"""
Transport Slice Demo — Standalone OVS
======================================
Shows a complete transport slice: SRv6 path enforcement + OVS bandwidth guarantee.

Topology:
    h1 (10.0.0.1) ──┐
                    s1 ──[10 Mbps]── s2 ──── h2  (10.0.0.2)
    h3 (10.0.0.3) ──┘                └───── mb1 (10.0.0.4)

SRv6 SIDs:
    h1  → fc00::1
    h2  → fc00::2
    mb1 → fc00::b1

Premium slice contract:
    Path:      h1 → mb1 → h2   (SRv6 enforced detour via mb1)
    Bandwidth: 8 Mbps           (OVS HTB queue on s1→s2 bottleneck)

Demo phases:
    Phase 1 — Baseline
              h1→h2 at 8 Mbps, direct path.
              mb1 logger is RUNNING but SILENT — traffic bypasses it.

    Phase 2 — Contention
              h3 floods at 8 Mbps. h1 drops to ~5 Mbps (fair share).
              mb1 logger still SILENT — no slice, no path enforcement.

    Phase 3 — Provision slice
              OVS queue installed (8 Mbps guarantee).
              SRv6 route installed on h1 (h1 → mb1 → h2).
              h1 recovers to ~8 Mbps AND mb1 logger lights up.

    Phase 4 — Teardown slice
              Queue and SRv6 route removed atomically.
              h1 drops back to ~5 Mbps AND mb1 goes silent.

Controller: Standalone OVS (no ONOS required)

Usage:
    sudo python3 slice_demo.py
"""

import sys
import time

from mininet.net import Mininet
from mininet.node import OVSKernelSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI


# ─── SRv6 SID table ───────────────────────────────────────────────────────────

SID = {
    "h1":  "fc00::1",
    "h2":  "fc00::2",
    "mb1": "fc00::b1",
}
SID_SUBNET = "fc00::/64"

MB1_LOG = "/tmp/mb1_bandwidth.log"

H1_PORT = 5201   # iperf3 server port for h1 traffic
H3_PORT = 5202   # iperf3 server port for h3 traffic


# ─── Topology ─────────────────────────────────────────────────────────────────

def build_topology(net):
    info("*** Adding hosts\n")
    h1  = net.addHost("h1",  ip="10.0.0.1/24", mac="00:00:00:00:00:01")
    h2  = net.addHost("h2",  ip="10.0.0.2/24", mac="00:00:00:00:00:02")
    h3  = net.addHost("h3",  ip="10.0.0.3/24", mac="00:00:00:00:00:03")
    mb1 = net.addHost("mb1", ip="10.0.0.4/24", mac="00:00:00:00:00:04")

    info("*** Adding switches\n")
    s1 = net.addSwitch("s1", cls=OVSKernelSwitch, failMode="standalone")
    s2 = net.addSwitch("s2", cls=OVSKernelSwitch, failMode="standalone")

    info("*** Adding links\n")
    net.addLink(h1,  s1, cls=TCLink, bw=100, delay="1ms")
    net.addLink(h3,  s1, cls=TCLink, bw=100, delay="1ms")
    net.addLink(h2,  s2, cls=TCLink, bw=100, delay="1ms")
    net.addLink(mb1, s2, cls=TCLink, bw=100, delay="1ms")
    net.addLink(s1,  s2, cls=TCLink, bw=10,  delay="5ms")  # BOTTLENECK

    return h1, h2, h3, mb1, s1, s2


# ─── SRv6 helpers ─────────────────────────────────────────────────────────────

def configure_srv6_host(host, sid, all_hosts):
    """
    Enable SRv6, assign SID, add on-link subnet route, and install
    static IPv6 neighbour entries so forwarding works without NDP.
    """
    iface = f"{host.name}-eth0"
    host.cmd("sysctl -w net.ipv6.conf.all.forwarding=1    > /dev/null")
    host.cmd("sysctl -w net.ipv6.conf.all.seg6_enabled=1  > /dev/null")
    host.cmd(f"sysctl -w net.ipv6.conf.{iface}.seg6_enabled=1 > /dev/null")
    host.cmd(f"ip -6 addr add {sid}/128 dev {iface} 2>/dev/null; true")
    host.cmd(f"ip -6 route add {SID_SUBNET} dev {iface} 2>/dev/null; true")
    for other_name, (other_sid, other_mac) in all_hosts.items():
        if other_name == host.name:
            continue
        host.cmd(
            f"ip -6 neigh replace {other_sid} lladdr {other_mac} "
            f"dev {iface} 2>/dev/null; true"
        )
    info(f"    {host.name}: SID={sid}\n")


def configure_all_srv6(h1, h2, mb1):
    info("*** Configuring SRv6 on hosts\n")
    all_hosts = {
        "h1":  (SID["h1"],  h1.MAC()),
        "h2":  (SID["h2"],  h2.MAC()),
        "mb1": (SID["mb1"], mb1.MAC()),
    }
    configure_srv6_host(h1,  SID["h1"],  all_hosts)
    configure_srv6_host(h2,  SID["h2"],  all_hosts)
    configure_srv6_host(mb1, SID["mb1"], all_hosts)
    time.sleep(2)   # wait for DAD to complete


def verify_srv6(h1):
    info("*** Verifying SRv6 SID reachability\n")
    ok = True
    for name, sid in SID.items():
        if name == "h1":
            continue
        rc = h1.cmd(f"ping6 -c 1 -W 2 {sid} > /dev/null 2>&1; echo $?").strip()
        reachable = rc == "0"
        info(f"    h1 → {name} ({sid}): {'✓' if reachable else '✗'}\n")
        ok = ok and reachable
    return ok


def install_srv6_route(h1, dst_ipv4, segments):
    segs = ",".join(segments)
    h1.cmd(
        f"ip route replace {dst_ipv4} "
        f"encap seg6 mode encap segs {segs} dev h1-eth0"
    )
    info(f"    SRv6 encap: {dst_ipv4} via {segs}\n")


def remove_srv6_route(h1, dst_ipv4):
    h1.cmd(f"ip route del {dst_ipv4} 2>/dev/null; true")
    info(f"    SRv6 route removed — {dst_ipv4} back to direct path\n")


# ─── OVS queue helpers ────────────────────────────────────────────────────────

def get_iface_facing(switch, peer_name):
    for intf in switch.intfList():
        if intf.link:
            other = (intf.link.intf2 if intf.link.intf1 == intf
                     else intf.link.intf1)
            if other.node.name == peer_name:
                return intf.name
    raise RuntimeError(f"No link between {switch.name} and {peer_name}")


def get_ofport(switch, iface):
    return switch.cmd(f"ovs-vsctl get Interface {iface} ofport").strip()


def setup_ovs_queues(s1):
    iface = get_iface_facing(s1, "s2")
    info(f"*** Provisioning OVS queues on {iface}\n")

    s1.cmd(f"ovs-vsctl clear port {iface} qos")
    s1.cmd("ovs-vsctl --all destroy qos   2>/dev/null; true")
    s1.cmd("ovs-vsctl --all destroy queue 2>/dev/null; true")

    s1.cmd(
        f'ovs-vsctl set port {iface} qos=@newqos -- '
        f'--id=@newqos create qos type=linux-htb '
        f'other-config:max-rate=10000000 '
        f'queues:0=@q0 queues:1=@q1 -- '
        f'--id=@q0 create queue '
        f'other-config:min-rate=1000000 '
        f'other-config:max-rate=10000000 '
        f'other-config:burst=125000 -- '
        f'--id=@q1 create queue '
        f'other-config:min-rate=8000000 '
        f'other-config:max-rate=8000000 '
        f'other-config:burst=62500'
    )

    bottleneck_ofport = get_ofport(s1, iface)
    h1_iface  = get_iface_facing(s1, "h1")
    h1_ofport = get_ofport(s1, h1_iface)
    info(f"    Q0: best-effort  Q1: 8 Mbps  bottleneck={bottleneck_ofport} h1={h1_ofport}\n")
    return iface, bottleneck_ofport, h1_ofport


def install_queue_flow(s1, h1_mac, h1_ofport, bottleneck_ofport):
    """Steer h1 traffic into queue 1 using ovs-ofctl."""
    s1.cmd(
        f'ovs-ofctl add-flow s1 '
        f'priority=100,'
        f'in_port={h1_ofport},'
        f'dl_src={h1_mac},'
        f'actions=set_queue:1,normal'
    )
    info(f"    Queue flow: port={h1_ofport} src={h1_mac} → queue 1\n")


def teardown_ovs_queues(s1, h1_mac=None, h1_ofport=None):
    try:
        iface = get_iface_facing(s1, "s2")
        s1.cmd(f"ovs-vsctl clear port {iface} qos")
        s1.cmd("ovs-vsctl --all destroy qos   2>/dev/null; true")
        s1.cmd("ovs-vsctl --all destroy queue 2>/dev/null; true")

        # Delete only our queue steering rule — not all flows.
        # Wiping all flows resets MAC learning and breaks connectivity.
        if h1_mac and h1_ofport:
            s1.cmd(
                f"ovs-ofctl del-flows s1 "
                f"priority=100,in_port={h1_ofport},dl_src={h1_mac} "
                f"2>/dev/null; true"
            )

        # Restore the TC HTB shaper on the bottleneck interface.
        # ovs-vsctl clear qos disturbs the TC qdiscs that Mininet's TCLink
        # originally installed, leaving the link effectively unthrottled.
        _restore_tc_shaper(iface, bw_mbps=10)
        info("    OVS queues removed, TC shaper restored\n")
    except Exception as e:
        info(f"    (teardown warning: {e})\n")


def _restore_tc_shaper(iface, bw_mbps):
    """Re-apply a simple HTB shaper on iface at bw_mbps after OVS QoS teardown."""
    import subprocess
    bw_kbps  = bw_mbps * 1000
    burst_kb = bw_mbps * 2      # 2ms burst
    subprocess.run(f"tc qdisc del dev {iface} root 2>/dev/null; true",
                   shell=True)
    subprocess.run(
        f"tc qdisc add dev {iface} root handle 1: htb default 10 && "
        f"tc class add dev {iface} parent 1: classid 1:10 htb "
        f"rate {bw_kbps}kbit burst {burst_kb}kb",
        shell=True
    )


# ─── mb1 bandwidth logger ─────────────────────────────────────────────────────

def write_mb1_logger(script_path, log_path, h1_mac):
    """
    Logger counts only packets arriving FROM h1 (src MAC = h1_mac).
    This avoids double-counting: we see only the h1→h2 forward direction,
    not the return ACKs or the outbound copy heading to h2.
    SRv6 encap packets from h1 still carry h1's original src MAC at L2.
    """
    lines = [
        "#!/usr/bin/env python3\n",
        "import socket, time, sys, signal, struct\n",
        'IFACE   = "mb1-eth0"\n',
        'LOG     = "' + log_path + '"\n',
        'H1_MAC  = bytes.fromhex("' + h1_mac.replace(":", "") + '")\n',
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
        "                # Ethernet src MAC is bytes 6-12\n",
        "                if pkt[6:12] == H1_MAC:\n",
        "                    total += len(pkt)\n",
        "            except socket.timeout:\n",
        "                break\n",
        "        mbps = (total * 8) / 1_000_000\n",
        '        ts   = time.strftime("%H:%M:%S")\n',
        '        label = "  <- slice traffic" if mbps > 0.01 else ""\n',
        '        line  = f"[mb1] [{ts}]  {mbps:5.2f} Mbits/sec{label}\\n"\n',
        '        open(LOG, "a").write(line)\n',
        "        sys.stdout.write(line); sys.stdout.flush()\n",
        "\n",
        "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))\n",
        "loop()\n",
    ]
    with open(script_path, "w") as f:
        f.writelines(lines)


def start_mb1_logger(mb1, h1_mac):
    script = "/tmp/mb1_logger.py"
    write_mb1_logger(script, MB1_LOG, h1_mac)
    mb1.cmd("pkill -f mb1_logger 2>/dev/null; true")
    mb1.cmd(f"python3 {script} > /tmp/mb1_logger_stdout.log 2>&1 &")
    time.sleep(0.5)
    info(f"    mb1 logger started (filtering src={h1_mac}) → tail -F {MB1_LOG}\n")


def stop_mb1_logger(mb1):
    mb1.cmd("pkill -f mb1_logger 2>/dev/null; true")
    info("    mb1 logger stopped\n")


# ─── iperf3 helpers ───────────────────────────────────────────────────────────

def start_iperf_servers(h2):
    h2.cmd("pkill -f iperf3 2>/dev/null; true")
    time.sleep(0.3)
    h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
    h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
    time.sleep(0.5)
    info(f"*** iperf3 servers on h2 ports {H1_PORT} and {H3_PORT}\n")


def run_iperf_client(host, server_ip, mbps, port, tag, duration=600):
    host.cmd(
        f"iperf3 -c {server_ip} -p {port} -b {mbps}M "
        f"-t {duration} --forceflush -i 1 "
        f"2>&1 | tee /tmp/iperf_{tag}.log &"
    )


def stop_all(h1, h3, h2):
    h1.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
    h3.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
    h2.cmd("pkill -f iperf3      2>/dev/null; true")
    time.sleep(1)


# ─── Slice ────────────────────────────────────────────────────────────────────

def provision_slice(s1, h1, h2):
    info("\n*** Provisioning premium transport slice\n")
    iface, bottleneck_ofport, h1_ofport = setup_ovs_queues(s1)
    install_queue_flow(s1, h1.MAC(), h1_ofport, bottleneck_ofport)
    info("\n*** Installing SRv6 route on h1\n")
    install_srv6_route(h1, h2.IP(), [SID["mb1"], SID["h2"]])
    rc = h1.cmd(
        f"ping6 -c 2 -W 2 {SID['h2']} > /dev/null 2>&1; echo $?"
    ).strip()
    info(f"    Path check h1 → mb1 → h2: {'✓' if rc == '0' else '✗ WARNING'}\n")


def teardown_slice(s1, h1, h2):
    info("\n*** Tearing down premium transport slice\n")
    remove_srv6_route(h1, h2.IP())
    h1_iface  = get_iface_facing(s1, "h1")
    h1_ofport = get_ofport(s1, h1_iface)
    teardown_ovs_queues(s1, h1_mac=h1.MAC(), h1_ofport=h1_ofport)


# ─── Interactive demo ─────────────────────────────────────────────────────────

def interactive_demo(net, h1, h2, h3, mb1, s1, s2):
    sep = "=" * 64
    print(f"\n{sep}")
    print("  TRANSPORT SLICE DEMO  —  Standalone OVS")
    print(sep)
    print(f"""
Topology:
    h1 (10.0.0.1) ──┐
                    s1 ──[10 Mbps]── s2 ──── h2  (10.0.0.2)
    h3 (10.0.0.3) ──┘                └───── mb1 (10.0.0.4)

Open these in separate terminals before starting:
    tail -F /tmp/iperf_h1.log
    tail -F /tmp/iperf_h3.log
    tail -F {MB1_LOG}
    """)

    configure_all_srv6(h1, h2, mb1)

    info("*** Testing IPv4 connectivity\n")
    net.pingAll()
    verify_srv6(h1)
    start_iperf_servers(h2)

    # ── Phase 1 ──────────────────────────────────────────────────────────────
    input("\n[ Press ENTER ] ▶  PHASE 1: Start mb1 logger + h1→h2 baseline")
    print()

    info("*** Starting mb1 bandwidth logger\n")
    start_mb1_logger(mb1, h1.MAC())
    run_iperf_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")

    print(f"""
  Phase 1 — Baseline (no slice)
  ──────────────────────────────
  h1→h2 at 8 Mbps on the DIRECT path: h1 → s1 → s2 → h2

  mb1 logger is RUNNING but shows ~0.00 Mbits/sec.
  Traffic bypasses mb1 completely without SRv6.

    tail -F /tmp/iperf_h1.log     → ~8 Mbps
    tail -F {MB1_LOG} → SILENCE
    """)

    # ── Phase 2 ──────────────────────────────────────────────────────────────
    input("[ Press ENTER ] ▶  PHASE 2: h3 floods — contention on bottleneck")
    print()

    run_iperf_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")

    print(f"""
  Phase 2 — Contention (no slice)
  ────────────────────────────────
  h3→h2 at 8 Mbps. TCP fair-share → both get ~5 Mbps.
  mb1 logger still SILENT.

    tail -F /tmp/iperf_h1.log     → drops to ~5 Mbps
    tail -F /tmp/iperf_h3.log     → ~5 Mbps
    tail -F {MB1_LOG} → SILENCE
    """)

    # ── Phase 3 ──────────────────────────────────────────────────────────────
    input("[ Press ENTER ] ▶  PHASE 3: Provision premium transport slice")
    print()

    stop_all(h1, h3, h2)
    provision_slice(s1, h1, h2)
    start_iperf_servers(h2)
    time.sleep(0.5)
    run_iperf_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
    time.sleep(0.5)
    run_iperf_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")

    print(f"""
  Phase 3 — Premium slice ACTIVE
  ────────────────────────────────
  ┌────────────────────────────────────────────────────────┐
  │  Path contract:      h1 → mb1 → h2   (SRv6)           │
  │  Bandwidth contract: 8 Mbps guaranteed (OVS HTB queue) │
  └────────────────────────────────────────────────────────┘

    tail -F /tmp/iperf_h1.log     → recovers to ~8 Mbps  ✅
    tail -F /tmp/iperf_h3.log     → drops to ~2 Mbps
    tail -F {MB1_LOG} → SHOWS TRAFFIC  ✅

  Both contracts active simultaneously.
  SRv6 path guarantee is hard — h1 ALWAYS visits mb1.
  Queue bandwidth guarantee is soft — ~8 Mbps average.
  Occasional retransmit spikes = soft slicing in action.
    """)

    # ── Phase 4 ──────────────────────────────────────────────────────────────
    input("[ Press ENTER ] ▶  PHASE 4: Teardown slice — back to best-effort")
    print()

    stop_all(h1, h3, h2)
    teardown_slice(s1, h1, h2)
    start_iperf_servers(h2)
    time.sleep(0.5)
    run_iperf_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
    time.sleep(0.5)
    run_iperf_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")

    print(f"""
  Phase 4 — Slice torn down
  ───────────────────────────
  Queue removed. SRv6 route removed. Back to best-effort.

    tail -F /tmp/iperf_h1.log     → drops to ~5 Mbps
    tail -F /tmp/iperf_h3.log     → back to ~5 Mbps
    tail -F {MB1_LOG} → goes SILENT

  Without the slice:
    No bandwidth protection — h1 gets fair share only.
    No path enforcement   — traffic bypasses mb1.
    """)

    input("[ Press ENTER ] ▶  Open Mininet CLI (type 'exit' to finish)")
    CLI(net)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    setLogLevel("info")

    net = Mininet(
        controller=None,
        switch=OVSKernelSwitch,
        link=TCLink,
        autoSetMacs=False,
    )
    # No controller needed — switches use failMode=standalone (built-in MAC learning)
    h1, h2, h3, mb1, s1, s2 = build_topology(net)

    info("*** Starting network\n")
    net.start()

    try:
        interactive_demo(net, h1, h2, h3, mb1, s1, s2)
    finally:
        info("\n*** Cleaning up\n")
        for h in [h1, h2, h3, mb1]:
            h.cmd("pkill -f iperf3     2>/dev/null; true")
            h.cmd("pkill -f mb1_logger 2>/dev/null; true")
        try:
            teardown_ovs_queues(s1)   # best-effort cleanup, MAC table wipe ok on exit
        except Exception:
            pass
        info("*** Stopping network\n")
        net.stop()


if __name__ == "__main__":
    main()