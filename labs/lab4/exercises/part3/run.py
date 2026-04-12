#!/usr/bin/env python3
"""
Exercise 3 — Admission Control
==============================

Goal:
  Observe that not every slice request can be admitted once bandwidth is
  already reserved on the direct bottleneck.

Workflow:
  1. Start this runner.
  2. When prompted, edit `exercises/part3/slice_request.py`.
  3. Return here and press Enter to load your request.

Usage:
    sudo python3 exercises/part3/run.py
"""

import sys
from pathlib import Path

LAB4_DIR = Path(__file__).resolve().parents[2]
if str(LAB4_DIR) not in sys.path:
    sys.path.insert(0, str(LAB4_DIR))

from _internal.exercise_common import run_admission_control_exercise
from _internal.controller import MB1_LOG


BASELINE_SLICE_REQUEST = {
    "name": "premium",
    "src": "h1",
    "dst": "h2",
    "latency_objective": "standard",
    "bandwidth_mbps": 8,
    "waypoints": ["mb1"],
}

REQUEST_PATH = Path(__file__).with_name("slice_request.py")


def main():
    run_admission_control_exercise(
        title="Exercise 3 — Admission Control",
        intro="""
The controller will first install a fixed premium slice for h1.
Your request then competes for the remaining bandwidth on the direct bottleneck.
""".strip(),
        baseline_request=BASELINE_SLICE_REQUEST,
        request_path=REQUEST_PATH,
        tail_paths=("/tmp/iperf_h1.log", "/tmp/iperf_h3.log", MB1_LOG),
    )


if __name__ == "__main__":
    main()
