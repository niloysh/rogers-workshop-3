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
        after_apply_text=f"""
Observe the result:

  tail -F /tmp/iperf_h1.log   -> ?
  tail -F /tmp/iperf_h3.log   -> ?
  tail -F {PING_LOG} -> ?
  tail -F {MB1_LOG} -> ?

Questions:
  - Did h1 get off the direct bottleneck?
  - Did the RTT settle near ~20 ms after the request was applied?
  - Why did h3's throughput change?
  - Which field in SLICE_REQUEST expressed the path objective?
  - Which waypoint corresponds to the telemetry monitor?
""",
        after_teardown_text=f"""
Slice removed. What do you see now?

  tail -F /tmp/iperf_h1.log   -> ?
  tail -F /tmp/iperf_h3.log   -> ?
  tail -F {PING_LOG} -> ?
  tail -F {MB1_LOG} -> ?

Why did the behavior revert?
""",
    )


if __name__ == "__main__":
    main()
