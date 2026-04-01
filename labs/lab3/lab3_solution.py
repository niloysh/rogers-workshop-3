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
  mininet> h2 ip route add 10.0.0.1 encap seg6 mode encap \\
             segs fc00::b2,fc00::b1,fc00::1 dev h2-eth0
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
    # With mode encap, the original IPv4 packet stays inside a new outer
    # IPv6+SRH transport packet. The segs list includes the final SRv6
    # destination as well as the waypoints.
    rc = run(
        "ip route replace 10.0.0.1 "
        "encap seg6 mode encap "
        "segs fc00::b2,fc00::b1,fc00::1 "
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
    run("ip route show")

    print("""
[solution] Explanation:
  The reverse chain is h2 → mb2 → mb1 → h1.
  mb2 (IDS) is visited before mb1 (waypoint 1) in the reverse direction.

  Why this order?
    In the forward direction, traffic visits mb1 then mb2 before h2.
    In the reverse direction, we mirror that chain from the h2 side:
      - traffic leaves h2 and reaches mb2 first
      - then it passes through mb1
      - then it arrives at h1

    If the order were reversed:
      - the return path would no longer mirror the intended service chain
      - mb2 would not be the first inspection point on the way back
      - your reverse-path capture would show a different service order

[solution] Test commands:
  Open a shell in mb1 from a regular shell:
    ./enter_host.sh mb1
  Then inside mb1:
    tshark -i mb1-eth0 -Y "icmp && ip.addr==10.0.0.1 && ip.addr==10.0.0.2"
  And from Mininet CLI:
    mininet> h1 ping -c 3 10.0.0.2

  Before the reverse route:
    - mb1 mainly sees only the echo requests
  After the reverse route:
    - mb1 sees both the echo requests and the echo replies
""")


if __name__ == '__main__':
    main()
