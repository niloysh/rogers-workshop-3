#!/usr/bin/env python3
"""
Learner-facing slice request abstraction for Lab 4.

Participants describe what they want:
  - latency objective
  - bandwidth objective
  - service-chain waypoints

This module translates that request into the controller's lower-level
SRv6 chain and queue parameters.
"""

VALID_LATENCY_OBJECTIVES = ("standard", "low")


def realize_slice_request(slice_request):
    """Validate a learner-facing request and map it to controller inputs."""
    required = (
        "name",
        "src",
        "dst",
        "latency_objective",
        "bandwidth_mbps",
        "waypoints",
    )
    missing = [field for field in required if field not in slice_request]
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")

    latency_objective = slice_request["latency_objective"]
    if latency_objective not in VALID_LATENCY_OBJECTIVES:
        valid = ", ".join(VALID_LATENCY_OBJECTIVES)
        raise ValueError(
            f"Unsupported latency_objective '{latency_objective}'. "
            f"Use one of: {valid}"
        )

    waypoints = list(slice_request["waypoints"])
    for waypoint in waypoints:
        if waypoint in ("r1", "r1b"):
            raise ValueError(
                "Do not list 'r1' or 'r1b' in waypoints. "
                "Use latency_objective='low' to request the alternate path."
            )

    bandwidth_mbps = slice_request["bandwidth_mbps"]
    if not isinstance(bandwidth_mbps, (int, float)) or bandwidth_mbps < 0:
        raise ValueError("bandwidth_mbps must be a non-negative number")

    chain = list(waypoints)
    if latency_objective == "low":
        chain = ["r1"] + chain

    reverse_map = {
        "r1": "r1b",
        "r1b": "r1",
    }
    reverse_chain = [reverse_map.get(waypoint, waypoint) for waypoint in reversed(chain)]

    return {
        "name": slice_request["name"],
        "src": slice_request["src"],
        "dst": slice_request["dst"],
        "latency_objective": latency_objective,
        "bandwidth_mbps": bandwidth_mbps,
        "waypoints": waypoints,
        "chain": chain,
        "reverse_chain": reverse_chain,
    }


def format_slice_request(slice_request, heading="Slice Request"):
    """Return a short learner-friendly rendering of the requested service."""
    realized = realize_slice_request(slice_request)
    waypoints = ", ".join(realized["waypoints"]) if realized["waypoints"] else "(none)"
    return "\n".join([
        f"{heading}:",
        f"  name:               {realized['name']}",
        f"  src -> dst:         {realized['src']} -> {realized['dst']}",
        f"  latency_objective:  {realized['latency_objective']}",
        f"  bandwidth_mbps:     {realized['bandwidth_mbps']}",
        f"  waypoints:          {waypoints}",
    ])


def format_slice_realization(slice_request, heading="Controller Realization"):
    """Return the implementation details that satisfy the learner request."""
    realized = realize_slice_request(slice_request)
    forward = " -> ".join([realized["src"]] + realized["chain"] + [realized["dst"]])
    reverse = " -> ".join([realized["dst"]] + realized["reverse_chain"] + [realized["src"]])
    queue = f"{realized['bandwidth_mbps']} Mbps" if realized["bandwidth_mbps"] > 0 else "none"
    return "\n".join([
        f"{heading}:",
        f"  forward path:       {forward}",
        f"  reverse path:       {reverse}",
        f"  queue guarantee:    {queue}",
    ])


def apply_slice_request(sc, slice_request):
    """Provision a controller slice from a learner-facing request."""
    realized = realize_slice_request(slice_request)
    sc.provision(
        realized["name"],
        src=realized["src"],
        dst=realized["dst"],
        chain=realized["chain"],
        bw=realized["bandwidth_mbps"],
    )
    return realized


def teardown_slice_request(sc, slice_request):
    """Remove a provisioned controller slice from a learner-facing request."""
    realized = realize_slice_request(slice_request)
    sc.teardown(realized["name"])
