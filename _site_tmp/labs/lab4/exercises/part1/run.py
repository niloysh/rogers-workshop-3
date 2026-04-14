#!/usr/bin/env python3
"""
Exercise 1 — Low-Latency Slice Request
======================================

Goal:
  Ask for a lower-latency service from h1 to h2 while still visiting the
  telemetry monitor.

Workflow:
  1. Start this runner.
  2. When prompted, edit `exercises/part1/slice_request.py`.
  3. Return here and press Enter to load your request.

Usage:
    sudo python3 exercises/part1/run.py
"""

import sys
from pathlib import Path

LAB4_DIR = Path(__file__).resolve().parents[2]
if str(LAB4_DIR) not in sys.path:
    sys.path.insert(0, str(LAB4_DIR))

from _internal.exercise_common import run_single_slice_exercise
from _internal.controller import MB1_LOG


REQUEST_PATH = Path(__file__).with_name("slice_request.py")
PING_LOG = "/tmp/ping_h1_h2.log"


def main():
    run_single_slice_exercise(
        title="Exercise 1 — Low-Latency Slice Request",
        intro="""
Use the topology roles above to decide how to express a lower-latency service.
Keep the telemetry monitor in the service chain, and leave the controller code alone.
""".strip(),
        request_path=REQUEST_PATH,
        logger_waypoints=("mb1",),
        tail_paths=("/tmp/iperf_h1.log", "/tmp/iperf_h3.log", PING_LOG, MB1_LOG),
        ping_watch={"source": "h1", "target": "h2", "tag": "h1_h2"},
        before_apply_text=f"""
  Phase 1 — Contention (no slice)
  ────────────────────────────────
  h1 and h3 both share the 10 Mbps direct bottleneck (s1→s2).
  Contention degrades BOTH bandwidth AND latency:

    tail -F /tmp/iperf_h1.log   → h1 gets ~5 Mbps
    tail -F /tmp/iperf_h3.log   → h3 gets ~5 Mbps
    tail -F {PING_LOG} → RTT climbs above 60 ms (queue builds up)
    tail -F {MB1_LOG} → SILENCE (no slice, no SRv6)
""",
        after_apply_text=f"""
  Phase 2 — Low-latency slice ACTIVE
  ────────────────────────────────────
  h1's traffic is SRv6-steered off the bottleneck, through the
  alternate r1 path (5 ms + 5 ms) and the telemetry monitor (mb1).

    tail -F /tmp/iperf_h1.log   → h1 recovers toward ~8 Mbps (uncongested path)
    tail -F /tmp/iperf_h3.log   → h3 gets the full 10 Mbps to itself
    tail -F {PING_LOG} → RTT drops to ~20 ms  (ping follows h1's new path)
    tail -F {MB1_LOG} → SHOWS TRAFFIC (mb1 in the chain)

  Questions:
    - Which field in SLICE_REQUEST moved h1 off the direct path?
    - Why does h3's throughput improve when h1 leaves the bottleneck?
    - Why does the RTT drop so sharply — is it only about congestion, or also path length?
""",
        after_teardown_text=f"""
  Phase 3 — Slice torn down
  ──────────────────────────
  SRv6 route removed. h1 falls back to the direct bottleneck.

    tail -F /tmp/iperf_h1.log   → h1 drops back to ~5 Mbps
    tail -F /tmp/iperf_h3.log   → h3 drops back to ~5 Mbps
    tail -F {PING_LOG} → RTT climbs back up (queue rebuilds under contention)
    tail -F {MB1_LOG} → SILENT again

  The network reverted because the slice was the only thing enforcing the path.
  Without it, ONOS reactive forwarding puts both flows back on the shortest path.
""",
    )


if __name__ == "__main__":
    main()
