#!/usr/bin/env python3
"""
slice_demo.py
─────────────
Interactive transport slice demo using SliceController.

Topology:
    h1 (10.0.0.1) ──┐
                    s1 ──[10 Mbps]── s2 ──── h2  (10.0.0.2)
    h3 (10.0.0.3) ──┘                └───── mb1 (10.0.0.4)

Usage:
    sudo python3 slice_demo.py
"""

import time
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI

from slice_controller import SliceController, MB1_LOG

H1_PORT = 5201
H3_PORT = 5202


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
    net.addLink(s1,  s2, cls=TCLink, bw=10,  delay="5ms")
    return h1, h2, h3, mb1, s1, s2


def start_servers(h2):
    h2.cmd("pkill -f iperf3 2>/dev/null; true")
    time.sleep(0.3)
    h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
    h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
    time.sleep(0.5)


def start_client(host, server_ip, mbps, port, tag, duration=600):
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


def run_demo(net, h1, h2, h3, mb1, s1, s2):
    sep = "=" * 64
    print(f"\n{sep}")
    print("  TRANSPORT SLICE DEMO")
    print(sep)
    print(f"""
Topology:
    h1 (10.0.0.1) ──┐
                    s1 ──[10 Mbps]── s2 ──── h2  (10.0.0.2)
    h3 (10.0.0.3) ──┘                └───── mb1 (10.0.0.4)

Open these in separate terminals:
    tail -F /tmp/iperf_h1.log
    tail -F /tmp/iperf_h3.log
    tail -F {MB1_LOG}
    """)

    sc = SliceController(net, s1, s2, link_bw=10)
    sc.configure_srv6("h1", "h2", "h3", "mb1")

    info("*** Testing connectivity\n")
    net.pingAll()
    sc.verify_srv6("h1", "h2", "mb1")
    start_servers(h2)

    # Phase 1
    input("\n[ Press ENTER ] ▶  PHASE 1: Start mb1 logger + h1→h2 baseline")
    print()
    sc._start_mb1_logger(mb1)
    info(f"    mb1 logger running → tail -F {MB1_LOG}\n")
    start_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
    print(f"""
  Phase 1 — Baseline (no slice)
  ──────────────────────────────
  h1→h2 at 8 Mbps. Direct path: h1 → s1 → s2 → h2.
  mb1 logger RUNNING but SILENT — traffic bypasses mb1.

    tail -F /tmp/iperf_h1.log     → ~8 Mbps
    tail -F {MB1_LOG} → SILENCE
    """)

    # Phase 2
    input("[ Press ENTER ] ▶  PHASE 2: h3 floods — contention")
    print()
    start_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")
    print(f"""
  Phase 2 — Contention (no slice)
  ────────────────────────────────
  h3 joins at 8 Mbps. TCP fair-share → both get ~5 Mbps.
  mb1 logger still SILENT.

    tail -F /tmp/iperf_h1.log     → drops to ~5 Mbps
    tail -F /tmp/iperf_h3.log     → ~5 Mbps
    tail -F {MB1_LOG} → SILENCE
    """)

    # Phase 3
    input("[ Press ENTER ] ▶  PHASE 3: Provision premium slice")
    print()
    stop_all(h1, h3, h2)
    sc.provision("premium", src="h1", dst="h2", chain=["mb1"], bw=8)
    sc.status()
    start_servers(h2)
    time.sleep(0.5)
    start_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
    time.sleep(0.5)
    start_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")
    print(f"""
  Phase 3 — Premium slice ACTIVE
  ────────────────────────────────
  ┌────────────────────────────────────────────────────────┐
  │  Path contract:      h1 → mb1 → h2   (SRv6)            │
  │  Bandwidth contract: 8 Mbps guaranteed (OVS HTB queue) │
  └────────────────────────────────────────────────────────┘

    tail -F /tmp/iperf_h1.log     → recovers to ~8 Mbps
    tail -F /tmp/iperf_h3.log     → drops to ~2 Mbps
    tail -F {MB1_LOG} → SHOWS TRAFFIC
    """)

    # Phase 4
    input("[ Press ENTER ] ▶  PHASE 4: Teardown slice")
    print()
    stop_all(h1, h3, h2)
    sc.teardown("premium")
    sc.status()
    start_servers(h2)
    time.sleep(0.5)
    start_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
    time.sleep(0.5)
    start_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")
    print(f"""
  Phase 4 — Slice torn down
  ───────────────────────────
  Queue removed. SRv6 route removed. Back to best-effort.

    tail -F /tmp/iperf_h1.log     → drops to ~5 Mbps
    tail -F /tmp/iperf_h3.log     → ~5 Mbps
    tail -F {MB1_LOG} → SILENT
    """)

    input("[ Press ENTER ] ▶  Open Mininet CLI")
    CLI(net)


def main():
    setLogLevel("info")
    net = Mininet(controller=None, switch=OVSKernelSwitch,
                  link=TCLink, autoSetMacs=False)
    h1, h2, h3, mb1, s1, s2 = build_topology(net)
    info("*** Starting network\n")
    net.start()
    try:
        run_demo(net, h1, h2, h3, mb1, s1, s2)
    finally:
        info("\n*** Cleaning up\n")
        for h in [h1, h2, h3, mb1]:
            h.cmd("pkill -f iperf3    2>/dev/null; true")
            h.cmd("pkill -f mb_logger 2>/dev/null; true")
        net.stop()


if __name__ == "__main__":
    main()