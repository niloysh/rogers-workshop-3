#!/usr/bin/env python3
"""
verify.py — Lab 3 exercise checker
────────────────────────────────────
Checks that the reverse SRv6 route is correctly installed on h2.

Usage:
    sudo python3 exercises/verify.py

Prerequisites:
    - topology.py must be running
    - configure_srv6.py must have been run
    - Forward chain on h1 must be working
"""

import subprocess
import sys

PASS = '\033[92m✓\033[0m'
FAIL = '\033[91m✗\033[0m'

results = []


def check(name, passed, hint=''):
    status = PASS if passed else FAIL
    print(f"  {status} {name}")
    if not passed and hint:
        print(f"      hint: {hint}")
    results.append(passed)


def mn_run(host, cmd, timeout=10):
    try:
        r = subprocess.run(
            f"sudo mnexec -a $(pgrep -f 'mininet:{host}' | head -1) {cmd}",
            shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 1, '', str(e)


print("=" * 50)
print("  Lab 3 — Reverse Route Checker")
print("=" * 50)

# ── Check 1: SRv6 enabled on h2 ──────────────────────────────
print("\n[1] SRv6 enabled on h2")
rc, out, _ = mn_run('h2', "sysctl net.ipv6.conf.all.seg6_enabled")
check("h2: seg6_enabled = 1", 'seg6_enabled = 1' in out,
      "run: python3 configure_srv6.py")

# ── Check 2: h2 SID assigned ─────────────────────────────────
print("\n[2] SID assigned to h2")
rc, out, _ = mn_run('h2', "ip -6 addr show")
check("h2: SID fc00::2 assigned", 'fc00::2' in out,
      "run: python3 configure_srv6.py")

# ── Check 3: Reverse route on h2 ─────────────────────────────
print("\n[3] Reverse SRv6 route on h2")
rc, out, _ = mn_run('h2', "ip route show")
reverse_line = next((l for l in out.splitlines() if '10.0.0.1' in l), '')

check("h2 has a route to 10.0.0.1", bool(reverse_line),
      "fill in exercises/reverse_route.sh and run: sudo bash exercises/reverse_route.sh")
check("route uses seg6 encap", 'seg6' in reverse_line,
      "make sure DESTINATION and SEGS are filled in correctly")
check("route visits mb2 first (fc00::b2)", 'fc00::b2' in reverse_line,
      "segs order for h2 → mb2 → mb1 → h1 should start with fc00::b2")
check("route visits mb1 second (fc00::b1)", 'fc00::b1' in reverse_line,
      "include fc00::b1 in the segs list")
check("route includes final SID for h1 (fc00::1)", 'fc00::1' in reverse_line,
      "the segs list must end with fc00::1")

# ── Summary ──────────────────────────────────────────────────
passed = sum(results)
total = len(results)
print(f"\n{'─'*50}")
print(f"  Results: {passed}/{total} checks passed")
if passed == total:
    print(f"  {PASS} All checks passed!")
    print()
    print("  Next: observe both directions on mb1 with tshark")
    print("    ./enter_host.sh mb1")
    print('    tshark -i mb1-eth0 -Y "icmp && ip.addr==10.0.0.1 && ip.addr==10.0.0.2"')
    print("  Then from Mininet:")
    print("    mininet> h1 ping -c 3 10.0.0.2")
else:
    failed = total - passed
    print(f"  {FAIL} {failed} check(s) failed — see hints above")
    print(f"  Compare with: solutions/reverse_route.sh")
print(f"{'─'*50}\n")

sys.exit(0 if passed == total else 1)
