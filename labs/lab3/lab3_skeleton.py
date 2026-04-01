#!/usr/bin/env python3
"""
lab3_skeleton.py
────────────────
Independent challenge — Lab 3

Install a reverse SRv6 route on h2 so that reply traffic is also
steered through the service chain: h2 → mb2 → mb1 → h1

Prerequisites:
  - lab3_topology.py must be running
  - SRv6 must be configured on all hosts (forwarding + seg6 + SIDs)
  - Forward chain must already be working: h1 → mb1 → mb2 → h2

Tasks:
  1. Install the reverse SRv6 route on h2
  2. Verify reverse traffic reaches mb2 first
  3. Test that ping from h2 to h1 is blocked by mb1

Run from the Mininet CLI:
  mininet> h2 python3 lab3_skeleton.py

Or manually enter the commands from the Mininet CLI.
"""


def print_task():
    print("""
Lab 3 — Independent Challenge
══════════════════════════════

Current state:
  Forward chain:  h1 → mb1 → mb2 → h2  ✓ (already working)
  Reverse chain:  h2 → ???              ✗ (your task)

Goal:
  Install a reverse SRv6 route on h2 so that:
  h2 → mb2 → mb1 → h1

Commands to run from Mininet CLI (mininet> h2 ...):

  # TODO: Install reverse SRv6 route on h2
  # Hint: destination is fc00::1 (h1's SID)
  # Hint: segs order for h2 → mb2 → mb1 → h1 is ?

  h2 ip -6 route add _______ \\
    encap seg6 mode inline \\
    segs _______ \\
    dev h2-eth0

Verify:
  ./enter_host.sh mb2
  # then inside mb2:
  tshark -i mb2-eth0 -Y "ipv6.routing.type == 4" -c 2
  mininet> h2 ping6 -c 3 fc00::1      # should reach mb2 first, then be blocked by mb1

Explain in a comment below:
  Why does the reverse chain visit mb2 before mb1?
  What would happen if the order were reversed?

# TODO: your explanation here
""")


if __name__ == '__main__':
    print_task()
