#!/usr/bin/env python3
"""
slice_demo.py — Lab 4b
──────────────────────
Interactive transport slice demo with ONOS.

Prerequisites:
    ONOS running with openflow, fwd, and proxyarp apps active:
        onos> app activate org.onosproject.openflow
        onos> app activate org.onosproject.fwd
        onos> app activate org.onosproject.proxyarp
        onos> cfg set org.onosproject.fwd.ReactiveForwarding ipv6Forwarding true

Usage:
    sudo python3 slice_demo.py
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

from topology import Lab4bTopo, ONOS_IP, ONOS_PORT, BOTTLENECK_BW
from slice_controller import SliceController, MB1_LOG

H1_PORT = 5201
H3_PORT = 5202


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


def run_demo(net):
    h1  = net.get('h1')
    h2  = net.get('h2')
    h3  = net.get('h3')
    mb1 = net.get('mb1')
    s1  = net.get('s1')
    s2  = net.get('s2')

    sep = "=" * 64
    print(f"\n{sep}")
    print("  LAB 4b — TRANSPORT SLICE DEMO (ONOS)")
    print(sep)
    print(f"""
Topology:
    h1 ─┐                                      ┌─ h2
    h3 ─┤── s1 ──[30ms, {BOTTLENECK_BW} Mbps]── s2 ─┤── mb1
        │   │  [5ms]          [5ms]  │   └─ mb2
        │   └──────── r1 ────────────┘

Terminals to open:
    tail -F /tmp/iperf_h1.log
    tail -F /tmp/iperf_h3.log
    tail -F {MB1_LOG}
    """)

    print("[setup] Confirm ONOS has ipv6Forwarding enabled:")
    print("    onos> cfg set org.onosproject.fwd.ReactiveForwarding ipv6Forwarding true")
    input("\n[ Press ENTER once ONOS is ready ] ▶  Start demo\n")

    sc = SliceController(net, s1, s2, link_bw=BOTTLENECK_BW)
    sc.configure_srv6("h1", "h2", "h3", "mb1", "mb2", "r1")

    info("*** Testing IPv4 connectivity (populates ONOS MAC table)\n")
    net.pingAll()
    sc.verify_srv6("h1", "h2", "mb1")
    start_servers(h2)

    # ── Phase 1 — baseline ────────────────────────────────────────────────────

    input("\n[ Press ENTER ] ▶  PHASE 1: h1→h2 baseline (direct path, no slice)")
    print()
    sc._start_mb1_logger(mb1)
    start_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
    print(f"""
  Phase 1 — Baseline (no slice, no SRv6)
  ────────────────────────────────────────
  h1→h2 via the direct s1-s2 link (30 ms delay, {BOTTLENECK_BW} Mbps cap).
  mb1 logger RUNNING but SILENT — traffic bypasses mb1.

    tail -F /tmp/iperf_h1.log   → ~8 Mbps
    tail -F {MB1_LOG} → SILENCE
    """)

    # ── Phase 2 — contention ──────────────────────────────────────────────────

    input("[ Press ENTER ] ▶  PHASE 2: h3 floods — contention on bottleneck")
    print()
    start_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")
    print(f"""
  Phase 2 — Contention (no slice)
  ────────────────────────────────
  h3 joins at 8 Mbps. TCP fair-share on the {BOTTLENECK_BW} Mbps bottleneck.

    tail -F /tmp/iperf_h1.log   → drops to ~5 Mbps
    tail -F /tmp/iperf_h3.log   → ~5 Mbps
    tail -F {MB1_LOG} → SILENCE
    """)

    # ── Phase 3 — bandwidth contract (queue on s1-s2) ─────────────────────────

    input("[ Press ENTER ] ▶  PHASE 3: Provision premium slice (path + bandwidth)")
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
  Phase 3 — Premium slice ACTIVE (s1-s2 path)
  ─────────────────────────────────────────────
  ┌─────────────────────────────────────────────────────────┐
  │  Path contract:      h1 → mb1 → h2   (SRv6)             │
  │  Bandwidth contract: 8 Mbps guaranteed (OVS HTB queue)  │
  └─────────────────────────────────────────────────────────┘

  h1 still uses the s1-s2 link but its queue is protected.

    tail -F /tmp/iperf_h1.log   → recovers to ~8 Mbps
    tail -F /tmp/iperf_h3.log   → squeezed to ~2 Mbps
    tail -F {MB1_LOG} → SHOWS TRAFFIC
    """)

    # ── Phase 4 — path contract: steer via r1 (bypass bottleneck) ────────────

    input("[ Press ENTER ] ▶  PHASE 4: Add r1 to the segment list")
    print()
    stop_all(h1, h3, h2)
    sc.teardown("premium")
    sc.provision("premium-r1", src="h1", dst="h2", chain=["r1", "mb1"], bw=8)
    sc.status()
    start_servers(h2)
    time.sleep(0.5)
    start_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
    time.sleep(0.5)
    start_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")
    print(f"""
  Phase 4 — Premium slice via r1 (alternate path)
  ─────────────────────────────────────────────────
  ┌─────────────────────────────────────────────────────────────┐
  │  Path contract:      h1 → r1 → mb1 → h2   (SRv6 via r1)    │
  │  Bandwidth contract: 8 Mbps (queue on s1-s2, now bypassed)  │
  └─────────────────────────────────────────────────────────────┘

  h1 travels s1→r1→s2 (5ms+5ms) instead of s1→s2 (30ms).
  h1 leaves the bottleneck entirely — h3 gets the full {BOTTLENECK_BW} Mbps.

    tail -F /tmp/iperf_h1.log   → ~8 Mbps (bottleneck bypassed)
    tail -F /tmp/iperf_h3.log   → ~8 Mbps (bottleneck now uncontested)
    tail -F {MB1_LOG} → SHOWS TRAFFIC
    """)

    # ── Phase 5 — teardown ────────────────────────────────────────────────────

    input("[ Press ENTER ] ▶  PHASE 5: Teardown slice")
    print()
    stop_all(h1, h3, h2)
    sc.teardown("premium-r1")
    sc.status()
    start_servers(h2)
    time.sleep(0.5)
    start_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
    time.sleep(0.5)
    start_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")
    print(f"""
  Phase 5 — Slice torn down
  ───────────────────────────
  Queue removed. SRv6 route removed. Both back to best-effort on s1-s2.

    tail -F /tmp/iperf_h1.log   → drops to ~5 Mbps
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
        autoSetMacs=False,
        waitConnected=True,
    )

    info("*** Starting network\n")
    net.start()

    try:
        run_demo(net)
    finally:
        info("\n*** Cleaning up\n")
        for name in ['h1', 'h2', 'h3', 'mb1', 'mb2']:
            h = net.get(name)
            h.cmd("pkill -f iperf3    2>/dev/null; true")
            h.cmd("pkill -f mb_logger 2>/dev/null; true")
        net.stop()


if __name__ == "__main__":
    main()
