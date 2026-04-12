#!/usr/bin/env python3
"""
Fixed request used by the Lab 4 demo.

Inspect this file when the demo pauses after Phase 2.
You do not need to edit it.
"""

SLICE_REQUEST = {
    "name": "premium",
    "src": "h1",
    "dst": "h2",
    "latency_objective": "standard",
    "bandwidth_mbps": 8,
    "waypoints": ["mb1"],
}
