#!/usr/bin/env python3
"""
alternate_path_demo.py — Lab 4b
───────────────────────────────
Interactive alternate-path slice demo with ONOS.

This demo mirrors the Lab 3b Step 4 idea inside the Lab 4b topology:
  - baseline traffic uses the direct s1-s2 link
  - h3 can congest that 10 Mbps bottleneck
  - a path-only SRv6 slice steers h1 via r1 -> mb1 -> h2
  - the improvement comes from path separation, not queue reservation

Usage:
    sudo python3 alternate_path_demo.py
"""

import sys
import time
from pathlib import Path
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI

LAB4B_DIR = Path(__file__).resolve().parent
if str(LAB4B_DIR) not in sys.path:
    sys.path.insert(0, str(LAB4B_DIR))

from topology import Lab4bTopo, ONOS_IP, ONOS_PORT, BOTTLENECK_BW, print_topology_info
from slice_controller import SliceController, MB1_LOG
from demo_common import H1_PORT, H3_PORT, start_servers, start_client, stop_all, cleanup_demo_hosts


def run_demo(net):
    h1  = net.get('h1')
    h2  = net.get('h2')
    h3  = net.get('h3')
    mb1 = net.get('mb1')
    s1  = net.get('s1')
    s2  = net.get('s2')

    print_topology_info(include_details=False)
    print("  Interactive alternate-path demo via r1")
    print(f"""
This demo isolates path steering:
  - no queue reservation is installed on s1-s2
  - h1 is steered over r1 -> mb1 -> h2
  - h3 stays on the direct s1-s2 path

Terminals to open:
    tail -F /tmp/iperf_h1.log
    tail -F /tmp/iperf_h3.log
    tail -F {MB1_LOG}
    """)

    print("[setup] Confirm ONOS has ipv6Forwarding enabled:")
    print("    onos> cfg set org.onosproject.fwd.ReactiveForwarding ipv6Forwarding true")
    input("\n[ Press ENTER once ONOS is ready ] ▶  Start demo\n")

    sc = SliceController(net, s1, s2, link_bw=BOTTLENECK_BW)

    info("*** Testing IPv4 connectivity (populates ONOS MAC table)\n")
    net.pingAll()
    sc.configure_srv6("h1", "h2", "h3", "mb1", "mb2", "r1")
    sc.warmup_ndp("h1", "h2", "h3", "mb1", "mb2")
    sc.verify_srv6("h1", "h2", "mb1")
    start_servers(h2)

    # ── Phase 1 — baseline ────────────────────────────────────────────────────

    input("\n[ Press ENTER ] ▶  PHASE 1: h1→h2 baseline (direct path, no slice)")
    print()
    sc._start_mb1_logger(mb1)
    start_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
    print(f"""
  Phase 1 — Baseline (direct path, no slice)
  ───────────────────────────────────────────
  h1→h2 uses the direct s1-s2 link. There is no SRv6 steering yet.
  mb1 logger RUNNING but SILENT — traffic bypasses mb1.

    tail -F /tmp/iperf_h1.log   → ~8 Mbps
    tail -F {MB1_LOG} → SILENCE
    """)

    # ── Phase 2 — contention ──────────────────────────────────────────────────

    input("[ Press ENTER ] ▶  PHASE 2: h3 floods — contention on s1-s2")
    print()
    start_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")
    print(f"""
  Phase 2 — Contention (still no slice)
  ──────────────────────────────────────
  h1 and h3 now share the same {BOTTLENECK_BW} Mbps direct bottleneck.

    tail -F /tmp/iperf_h1.log   → drops to ~5 Mbps
    tail -F /tmp/iperf_h3.log   → ~5 Mbps
    tail -F {MB1_LOG} → SILENCE
    """)

    # ── Phase 3 — alternate path via r1 ──────────────────────────────────────

    input("[ Press ENTER ] ▶  PHASE 3: Provision alternate-path slice via r1")
    print()
    stop_all(h1, h3, h2)
    sc.provision("express", src="h1", dst="h2", chain=["r1", "mb1"], bw=0)
    sc.status()
    start_servers(h2)
    time.sleep(0.5)
    start_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
    time.sleep(0.5)
    start_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")
    print(f"""
  Phase 3 — Alternate-path slice ACTIVE
  ───────────────────────────────────────
  ┌────────────────────────────────────────────────────────┐
  │  Path contract:      h1 → r1 → mb1 → h2   (SRv6)      │
  │  Bandwidth contract: none (best-effort, bw=0)         │
  └────────────────────────────────────────────────────────┘

  h1 bypasses the slow s1-s2 bottleneck through r1.
  h3 stays on the direct link, so the flows stop competing.

    tail -F /tmp/iperf_h1.log   → recovers to ~8 Mbps
    tail -F /tmp/iperf_h3.log   → recovers to ~8 Mbps
    tail -F {MB1_LOG} → SHOWS TRAFFIC
    """)

    # ── Phase 4 — teardown ────────────────────────────────────────────────────

    input("[ Press ENTER ] ▶  PHASE 4: Teardown alternate-path slice")
    print()
    stop_all(h1, h3, h2)
    sc.teardown("express")
    sc.status()
    start_servers(h2)
    time.sleep(0.5)
    start_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
    time.sleep(0.5)
    start_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")
    print(f"""
  Phase 4 — Slice torn down
  ───────────────────────────
  h1 falls back to the direct s1-s2 path, so both flows share the bottleneck again.

    tail -F /tmp/iperf_h1.log   → drops back to ~5 Mbps
    tail -F /tmp/iperf_h3.log   → ~5 Mbps
    tail -F {MB1_LOG} → SILENT
    """)

    input("[ Press ENTER ] ▶  Open Mininet CLI (type 'exit' to finish)")
    CLI(net)


def main():
    setLogLevel("info")

    print(f"[Controller] Connecting to ONOS at {ONOS_IP}:{ONOS_PORT}")
    net = Mininet(
        topo=Lab4bTopo(),
        controller=lambda name: RemoteController(name, ip=ONOS_IP, port=ONOS_PORT),
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        waitConnected=True,
    )

    info("*** Starting network\n")
    net.start()

    try:
        run_demo(net)
    finally:
        info("\n*** Cleaning up\n")
        cleanup_demo_hosts(net)
        net.stop()


if __name__ == "__main__":
    main()
