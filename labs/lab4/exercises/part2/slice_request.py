#!/usr/bin/env python3
"""
Editable request for Exercise 2.

Goal: keep traffic on the standard path but route it through both
      the telemetry monitor AND the security inspector before it reaches h2.

Schema reference
----------------
name              : any string — label for this slice
src / dst         : "h1" | "h2" | "h3"
latency_objective : "standard"  — stay on the direct s1→s2 path (30 ms, 10 Mbps cap)
                    "low"        — steer onto the alternate r1 path (5+5 ms, uncongested)
bandwidth_mbps    : 0           — best-effort (no queue reservation)
                    1–10        — guaranteed Mbps on the direct bottleneck
waypoints         : []                — no middlebox
                    ["mb1"]          — telemetry monitor only
                    ["mb2"]          — security inspector only
                    ["mb1", "mb2"]   — telemetry then security
                    ["mb2", "mb1"]   — security then telemetry
"""

# ============================================================
# TODO START
# Edit only the SLICE_REQUEST block below.
# Do not change the rest of the file.
# ============================================================
SLICE_REQUEST = {
    "name": "inspection",
    "src": "h1",
    "dst": "h2",
    "latency_objective": "standard",
    "bandwidth_mbps": 0,
    "waypoints": ["mb1"],              # <-- change this
}
# ============================================================
# TODO END
# ============================================================
