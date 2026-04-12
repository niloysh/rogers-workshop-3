#!/usr/bin/env python3
"""
run.py — Lab 4 demo
───────────────────
Interactive direct-path slice demo with ONOS.

Participants should focus on the request file:
  demo/slice_request.py

Prerequisites:
    ONOS running with openflow, fwd, and proxyarp apps active:
        onos> app activate org.onosproject.openflow
        onos> app activate org.onosproject.fwd
        onos> app activate org.onosproject.proxyarp
        onos> cfg set org.onosproject.fwd.ReactiveForwarding ipv6Forwarding true

Usage:
    sudo python3 demo/run.py
"""

import importlib.util
import sys
import time
from pathlib import Path
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI

LAB4_DIR = Path(__file__).resolve().parents[1]
if str(LAB4_DIR) not in sys.path:
    sys.path.insert(0, str(LAB4_DIR))

from _internal.topology import Lab4Topo, ONOS_IP, ONOS_PORT, BOTTLENECK_BW, print_topology_info
from _internal.controller import SliceController, MB1_LOG
from _internal.demo_common import H1_PORT, H3_PORT, start_servers, start_client, stop_all, cleanup_demo_hosts
from _internal.slice_request import (
    apply_slice_request,
    format_slice_realization,
    format_slice_request,
    realize_slice_request,
    teardown_slice_request,
)


REQUEST_PATH = Path(__file__).with_name("slice_request.py")


def _load_slice_request(request_path):
    request_path = Path(request_path).resolve()
    module_name = f"lab4_demo_request_{request_path.stat().st_mtime_ns}"
    spec = importlib.util.spec_from_file_location(module_name, request_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load request file: {request_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "SLICE_REQUEST"):
        raise ValueError("Request file must define SLICE_REQUEST")

    slice_request = module.SLICE_REQUEST
    if not isinstance(slice_request, dict):
        raise ValueError("SLICE_REQUEST must be a dictionary")
    return slice_request


def _inspect_request(request_path):
    display_path = request_path.resolve().relative_to(LAB4_DIR)

    print("Stop here and inspect the demo request before the slice is applied.")
    print()
    print("Open this file now:")
    print(f"  {display_path}")
    print()
    print("Read the SLICE_REQUEST block, predict what will happen, then come back and press ENTER.\n")

    while True:
        input("[ Press ENTER ] ▶  Load the demo request")
        print()
        try:
            slice_request = _load_slice_request(request_path)
            realize_slice_request(slice_request)
        except Exception as err:
            print(f"[request error] {err}")
            print(f"Fix {display_path} and press ENTER to try again.\n")
            continue

        print(format_slice_request(slice_request))
        print(format_slice_realization(slice_request))
        print()
        return slice_request


def run_demo(net):
    h1  = net.get('h1')
    h2  = net.get('h2')
    h3  = net.get('h3')
    mb1 = net.get('mb1')
    s1  = net.get('s1')
    s2  = net.get('s2')

    print_topology_info(include_details=False)
    print("  Interactive direct-path slice demo")
    print(f"""
The runner will pause after Phase 2 and ask you to inspect:
  demo/slice_request.py

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

    input("[ Press ENTER ] ▶  STOP: inspect the demo request")
    print()
    slice_request = _inspect_request(REQUEST_PATH)

    input("[ Press ENTER ] ▶  PHASE 3: Provision premium slice (path + bandwidth)")
    print()
    stop_all(h1, h3, h2)
    apply_slice_request(sc, slice_request)
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

  Connecting the Dots
  ───────────────────
  Lab 1 — programmable data plane
    The network's traffic treatment is not fixed. Realizing the slice changes
    how traffic is handled on the bottleneck.

  Lab 2 — SDN controller principle
    A transport slice controller takes one service request and turns it into
    concrete network actions, using ONOS-managed switches underneath.

  Lab 3 — SRv6 steering
    The slice forces h1's traffic through an explicit waypoint: mb1.
    """)

    # ── Phase 4 — teardown ────────────────────────────────────────────────────

    input("[ Press ENTER ] ▶  PHASE 4: Teardown slice")
    print()
    stop_all(h1, h3, h2)
    teardown_slice_request(sc, slice_request)
    sc.status()
    start_servers(h2)
    time.sleep(0.5)
    start_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
    time.sleep(0.5)
    start_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")
    print(f"""
  Phase 4 — Slice torn down
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
        topo=Lab4Topo(),
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
