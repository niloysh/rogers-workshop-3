#!/usr/bin/env python3
"""
lab3_solution.py
────────────────
Reference solution — Lab 3 independent challenge.

Installs the reverse SRv6 route on h2:
  h2 → mb2 → mb1 → h1

Run from the Mininet CLI after completing the guided lab:
  mininet> h2 python3 lab3_solution.py

Or manually:
  mininet> h2 ip -6 route add fc00::1 encap seg6 mode inline \\
             segs fc00::b2,fc00::b1 dev h2-eth0
"""

import subprocess
import sys


def run(cmd, host_cmd=True):
    """Run a command, optionally prefixed for clarity."""
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0 and result.stderr:
        print(f"  [error] {result.stderr.strip()}", file=sys.stderr)
    return result.returncode


def main():
    print("\n[solution] Installing reverse SRv6 route on h2...\n")

    # Install reverse route: h2 → mb2 → mb1 → h1
    # With mode inline, segs lists only the waypoints.
    # The final destination remains the packet's normal IPv6 destination.
    rc = run(
        "ip -6 route add fc00::1 "
        "encap seg6 mode inline "
        "segs fc00::b2,fc00::b1 "
        "dev h2-eth0"
    )

    if rc != 0:
        print("\n[solution] Route installation failed.")
        print("  Make sure SRv6 is configured on h2:")
        print("  sysctl -w net.ipv6.conf.all.forwarding=1")
        print("  sysctl -w net.ipv6.conf.all.seg6_enabled=1")
        print("  sysctl -w net.ipv6.conf.h2-eth0.seg6_enabled=1")
        print("  ip -6 addr add fc00::2/128 dev h2-eth0")
        sys.exit(1)

    print("\n[solution] Route installed. Verifying...\n")
    run("ip -6 route show")

    print("""
[solution] Explanation:
  The reverse chain is h2 → mb2 → mb1 → h1.
  mb2 (IDS) is visited before mb1 (firewall) in the reverse direction.

  Why this order?
    In the forward direction (h1→mb1→mb2→h2):
      - mb1 filters first (drop non-HTTP)
      - mb2 inspects what passes (log HTTP)

    In the reverse direction (h2→mb2→mb1→h1):
      - mb2 is still the first waypoint in the chain
      - mb1 then applies the same IPv6 forwarding policy on the reverse path

    If the order were reversed (mb1 before mb2):
      - mb1 would see the traffic before the IDS
      - for blocked traffic such as ICMPv6, mb1 could drop it before mb2
        ever sees it

    The principle: IDS sees more if placed before the firewall.
    The firewall ensures only permitted traffic continues past it.

[solution] Test commands:
  Open a shell in mb2 from a regular shell:
    ./enter_host.sh mb2
  Then inside mb2:
    tshark -i mb2-eth0 -Y "ipv6.routing.type == 4" -c 2
  And from Mininet CLI:
    mininet> h2 ping6 -c 3 fc00::1      # reaches mb2 first, then is BLOCKED by mb1
""")


if __name__ == '__main__':
    main()
