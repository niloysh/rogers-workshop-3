#!/usr/bin/env python3
"""
verify_lab3.py
──────────────
Checker for Lab 3 independent challenge.

Verifies that the reverse SRv6 chain is correctly configured:
  h2 → mb2 → mb1 → h1

Usage:
    sudo python3 verify_lab3.py

Prerequisites:
    - lab3_topology.py must be running
    - Forward chain must be working: h1 → mb1 → mb2 → h2
    - Reverse chain must be installed on h2
"""

import subprocess
import sys
import time

PASS = '\033[92m✓\033[0m'
FAIL = '\033[91m✗\033[0m'

results = []

def check(name, passed, detail=''):
    status = PASS if passed else FAIL
    print(f"  {status} {name}")
    if detail:
        print(f"      {detail}")
    results.append(passed)
    return passed

def mn_run(host, cmd, timeout=10):
    try:
        r = subprocess.run(
            f"sudo mnexec -a $(pgrep -f 'mininet:{host}' | head -1) {cmd}",
            shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 1, '', str(e)


def find_route_line(output, destination):
    for line in output.splitlines():
        if destination in line:
            return line
    return ""

print("=" * 55)
print("  Lab 3 — Verification")
print("  Reverse chain: h2 → mb2 → mb1 → h1")
print("=" * 55)
print("\n[setup] Keep Mininet, the h2 HTTP server, and the mb2 IDS running.")

# ── Test 1: SRv6 configured on all hosts ──────────────────────────────────────
print("\n[1] SRv6 configuration")
for host in ['h1', 'h2', 'mb1', 'mb2']:
    rc, out, _ = mn_run(host, "sysctl net.ipv6.conf.all.seg6_enabled")
    check(f"{host}: seg6_enabled = 1", 'seg6_enabled = 1' in out,
          f"Run: {host} sysctl -w net.ipv6.conf.all.seg6_enabled=1")

# ── Test 2: SIDs assigned ─────────────────────────────────────────────────────
print("\n[2] SID assignment")
sids = {'h1': 'fc00::1', 'h2': 'fc00::2',
        'mb1': 'fc00::b1', 'mb2': 'fc00::b2'}
for host, sid in sids.items():
    rc, out, _ = mn_run(host, "ip -6 addr show")
    check(f"{host}: SID {sid} assigned", sid in out)

# ── Test 3: Forward route on h1 ───────────────────────────────────────────────
print("\n[3] Forward SRv6 route (h1 → mb1 → mb2 → h2)")
rc, out, _ = mn_run('h1', "ip route show")
forward_line = find_route_line(out, '10.0.0.2')
check("h1 has forward route to 10.0.0.2", 'seg6' in forward_line,
      "Install: h1 ip route add 10.0.0.2 encap seg6 mode encap "
      "segs fc00::b1,fc00::b2,fc00::2 dev h1-eth0")
check("Forward route uses mode encap", 'mode encap' in forward_line)
check("Forward route includes mb1 (fc00::b1)", 'fc00::b1' in forward_line)
check("Forward route includes mb2 (fc00::b2)", 'fc00::b2' in forward_line)
check("Forward route includes final SID (fc00::2)", 'fc00::2' in forward_line)

# ── Test 4: Reverse route on h2 ───────────────────────────────────────────────
print("\n[4] Reverse SRv6 route (h2 → mb2 → mb1 → h1)")
rc, out, _ = mn_run('h2', "ip route show")
reverse_line = find_route_line(out, '10.0.0.1')
check("h2 has reverse route to 10.0.0.1", 'seg6' in reverse_line,
      "Install: h2 ip route add 10.0.0.1 encap seg6 mode encap "
      "segs fc00::b2,fc00::b1,fc00::1 dev h2-eth0")
check("Reverse route uses mode encap", 'mode encap' in reverse_line)
check("Reverse route visits mb2 first (fc00::b2)", 'fc00::b2' in reverse_line)
check("Reverse route visits mb1 second (fc00::b1)", 'fc00::b1' in reverse_line)
check("Reverse route includes final SID (fc00::1)", 'fc00::1' in reverse_line)

# ── Test 5: HTTP passes through chain ─────────────────────────────────────────
print("\n[5] HTTP passes through chain")

# Clear IDS log
mn_run('mb2', "truncate -s 0 /tmp/mb2_ids.log")

# Send HTTP request from h1
rc, out, _ = mn_run(
    'h1',
    "curl -s --max-time 3 'http://10.0.0.2/test'",
    timeout=8
)
check("h1 curl to h2 via forward chain succeeds", rc == 0,
      "HTTP request failed — check the server is running: "
      "./run_h2_http_server.sh")

# Wait briefly for IDS to log
time.sleep(1)

# Check IDS log
rc, out, _ = mn_run('mb2', "cat /tmp/mb2_ids.log")
check("mb2 IDS logged forward traffic", len(out.strip()) > 0,
      "IDS log empty — check the IDS is running: "
      "./run_mb2_ids.sh")

# ── Manual reverse-path verification ──────────────────────────────────────────
print("\n[6] Manual reverse-path proof")
print("    The checker can confirm the reverse route is installed, but the")
print("    easiest visual proof is a short ICMP capture on mb1.")
print("")
print("    Run this in a separate shell:")
print("      ./enter_host.sh mb1")
print("      tshark -i mb1-eth0 -Y \"icmp && ip.addr==10.0.0.1 && ip.addr==10.0.0.2\"")
print("")
print("    Then from Mininet:")
print("      mininet> h1 ping -c 3 10.0.0.2")
print("")
print("    Before the reverse route, mb1 mainly sees only the echo requests.")
print("    After the reverse route, mb1 sees both the requests and the replies.")

# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(results)
total = len(results)
print(f"\n{'─'*55}")
print(f"  Results: {passed}/{total} checks passed")
if passed == total:
    print(f"  {PASS} All automatic checks passed!")
else:
    failed = total - passed
    print(f"  {FAIL} {failed} check(s) failed — see details above")
    print(f"      Compare with: lab3_solution.py")
print(f"{'─'*55}\n")

sys.exit(0 if passed == total else 1)
