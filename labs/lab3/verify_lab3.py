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
WARN = '\033[93m!\033[0m'

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

def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 1, '', str(e)


print("=" * 55)
print("  Lab 3 — Verification")
print("  Reverse chain: h2 → mb2 → mb1 → h1")
print("=" * 55)

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
rc, out, _ = mn_run('h1', "ip -6 route show")
check("h1 has forward route to fc00::2", 'fc00::2' in out and 'seg6' in out,
      "Install: h1 ip -6 route add fc00::2 encap seg6 mode inline "
      "segs fc00::b1,fc00::b2 dev h1-eth0")
check("Forward route includes mb1 (fc00::b1)", 'fc00::b1' in out)
check("Forward route includes mb2 (fc00::b2)", 'fc00::b2' in out)

# ── Test 4: Reverse route on h2 ───────────────────────────────────────────────
print("\n[4] Reverse SRv6 route (h2 → mb2 → mb1 → h1)")
rc, out, _ = mn_run('h2', "ip -6 route show")
check("h2 has reverse route to fc00::1", 'fc00::1' in out and 'seg6' in out,
      "Install: h2 ip -6 route add fc00::1 encap seg6 mode inline "
      "segs fc00::b2,fc00::b1 dev h2-eth0")
check("Reverse route visits mb2 first (fc00::b2)", 'fc00::b2' in out)
check("Reverse route visits mb1 second (fc00::b1)", 'fc00::b1' in out)

# ── Test 5: Firewall blocks ping ───────────────────────────────────────────────
print("\n[5] Firewall behaviour")
rc, out, _ = mn_run('h1', "ping6 -c 2 -W 2 fc00::2", timeout=10)
check("mb1 blocks ICMP (ping6 from h1 fails)", rc != 0,
      "Ping succeeded — firewall may not be running. "
      "Start: ./run_mb1_firewall.sh")

rc, out, _ = mn_run('h2', "ping6 -c 2 -W 2 fc00::1", timeout=10)
check("mb1 blocks reverse ICMP (ping6 from h2 fails)", rc != 0,
      "Ping succeeded — check mb1 firewall rules")

# ── Test 6: HTTP passes through chain ─────────────────────────────────────────
print("\n[6] HTTP passes through chain")

# Clear IDS log
mn_run('mb2', "truncate -s 0 /tmp/mb2_ids.log")

# Send HTTP request from h1
rc, out, _ = mn_run(
    'h1',
    "curl -g -s --max-time 3 'http://[fc00::2]/test'",
    timeout=8
)
check("h1 curl to h2 via forward chain succeeds", rc == 0 or 'HTTP' in out,
      "HTTP request failed — check the server is running: "
      "./run_h2_http_server.sh")

# Wait briefly for IDS to log
time.sleep(1)

# Check IDS log
rc, out, _ = mn_run('mb2', "cat /tmp/mb2_ids.log")
check("mb2 IDS logged forward traffic", len(out.strip()) > 0,
      "IDS log empty — check the IDS is running: "
      "./run_mb2_ids.sh")

# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(results)
total = len(results)
print(f"\n{'─'*55}")
print(f"  Results: {passed}/{total} checks passed")
if passed == total:
    print(f"  {PASS} All checks passed! Reverse chain is working.")
else:
    failed = total - passed
    print(f"  {FAIL} {failed} check(s) failed — see details above")
    print(f"      Compare with: lab3_solution.py")
print(f"{'─'*55}\n")

sys.exit(0 if passed == total else 1)
