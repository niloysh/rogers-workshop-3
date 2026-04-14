#!/usr/bin/env python3
"""
Exercise 2 — Service-Chain Slice Request
=========================================

Goal:
  Stay on the standard path, but satisfy this service requirement:
    telemetry monitor -> security inspector -> destination

Workflow:
  1. Start this runner.
  2. When prompted, edit `exercises/part2/slice_request.py`.
  3. Return here and press Enter to load your request.

Usage:
    sudo python3 exercises/part2/run.py
"""

import sys
from pathlib import Path

LAB4_DIR = Path(__file__).resolve().parents[2]
if str(LAB4_DIR) not in sys.path:
    sys.path.insert(0, str(LAB4_DIR))

from _internal.exercise_common import run_single_slice_exercise
from _internal.controller import MB1_LOG, MB2_LOG


REQUEST_PATH = Path(__file__).with_name("slice_request.py")


def main():
    run_single_slice_exercise(
        title="Exercise 2 — Service-Chain Slice Request",
        intro="""
Use the topology roles above to express the needed service chain.
Keep the traffic best-effort and leave the controller code alone.
""".strip(),
        request_path=REQUEST_PATH,
        logger_waypoints=("mb1", "mb2"),
        tail_paths=("/tmp/iperf_h1.log", "/tmp/iperf_h3.log", MB1_LOG, MB2_LOG),
        after_apply_text=f"""
Observe the result:

  tail -F /tmp/iperf_h1.log   -> ?
  tail -F /tmp/iperf_h3.log   -> ?
  tail -F {MB1_LOG} -> ?
  tail -F {MB2_LOG} -> ?

Questions:
  - Which field in SLICE_REQUEST expressed the service chain?
  - Which host is the telemetry monitor? Which host is the security inspector?
  - Did the latency objective change?
  - Why are h1 and h3 still competing?
""",
        after_teardown_text=f"""
Slice removed. What do you see now?

  tail -F /tmp/iperf_h1.log   -> ?
  tail -F /tmp/iperf_h3.log   -> ?
  tail -F {MB1_LOG} -> ?
  tail -F {MB2_LOG} -> ?

What disappeared when the slice was removed?
""",
        verify_waypoints=("mb1", "mb2"),
    )


if __name__ == "__main__":
    main()
