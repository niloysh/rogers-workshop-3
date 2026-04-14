#!/usr/bin/env python3
"""
Editable request for Exercise 3.

Goal: submit a slice request for h3 that the admission controller will accept,
      given that h1 already holds an 8 Mbps reservation on the 10 Mbps bottleneck.

Hint: the controller rejects a request when the bandwidth it asks for exceeds
      the capacity that is still available on the bottleneck.

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
"""

# ============================================================
# TODO START
# Edit only the SLICE_REQUEST block below.
# Do not change the rest of the file.
# ============================================================
SLICE_REQUEST = {
    "name": "standard",
    "src": "h3",
    "dst": "h2",
    "latency_objective": "standard",
    "bandwidth_mbps": 5,               # <-- this will be rejected; adjust it
    "waypoints": [],
}
# ============================================================
# TODO END
# ============================================================
