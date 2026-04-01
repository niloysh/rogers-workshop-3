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
  2. Verify that ping replies now traverse mb1
  3. Explain why the reverse segs order is mb2 then mb1

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
  # Hint: destination is 10.0.0.1 (h1's IPv4 address)
  # Hint: outer segs order for h2 → mb2 → mb1 → h1 is ?

  h2 ip route add _______ \\
    encap seg6 mode encap \\
    segs _______ \\
    dev h2-eth0

Verify:
  ./enter_host.sh mb1
  # then inside mb1:
  tshark -i mb1-eth0 -Y "icmp && ip.addr==10.0.0.1 && ip.addr==10.0.0.2"
  mininet> h1 ping -c 3 10.0.0.2

  Before the reverse route:
    - you should mainly see only the echo requests on mb1
  After the reverse route:
    - you should see both echo requests and echo replies on mb1

Explain in a comment below:
  Why does the reverse chain visit mb2 before mb1?
  What would happen if the order were reversed?

# TODO: your explanation here
""")


if __name__ == '__main__':
    print_task()
