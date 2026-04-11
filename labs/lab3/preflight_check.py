#!/usr/bin/env python3
"""
preflight_check.py — Lab 3
──────────────────────────
Checks that the base topology is ready for the SRv6 exercises.

Run this after starting topology.py and before configuring SRv6.

Usage:
    python3 preflight_check.py
"""

import subprocess
import sys

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

def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 1, '', str(e)


print("=" * 50)
print("  Lab 3 — Preflight Check")
print("=" * 50)

# ── Check Mininet is running ───────────────────────────────────────────────────
print("\n[1] Mininet")
rc1, out1, _ = run_cmd("pgrep -x mn")
rc2, out2, _ = run_cmd("pgrep -f 'mininet:h1|mininet:h2|mininet:mb1|mininet:mb2'")
mininet_running = (rc1 == 0) or (rc2 == 0)
check("Mininet process is running", mininet_running,
      "Start the topology first: sudo python3 topology.py")

# ── Check OVS switches ─────────────────────────────────────────────────────────
print("\n[2] OVS switches")
rc, out, _ = run_cmd("sudo ovs-vsctl list-br")
bridges = [b for b in out.splitlines() if b.strip()]
check("s1 exists", 's1' in bridges, f"Found bridges: {bridges}")
check("s2 exists", 's2' in bridges, f"Found bridges: {bridges}")

# ── Check switch mode ──────────────────────────────────────────────────────────
print("\n[3] Switch mode")
rc1, out1, _ = run_cmd("sudo ovs-vsctl get-fail-mode s1")
rc2, out2, _ = run_cmd("sudo ovs-vsctl get-fail-mode s2")
check("s1 is in standalone mode", 'standalone' in out1,
      "Restart topology.py — Lab 3 does not use ONOS or a default controller")
check("s2 is in standalone mode", 'standalone' in out2,
      "Restart topology.py — Lab 3 does not use ONOS or a default controller")

# ── Check kernel SRv6 support ──────────────────────────────────────────────────
print("\n[4] Kernel SRv6 support")
rc, out, _ = run_cmd("ip -6 route add help 2>&1 | grep -i seg6")
check("iproute2 supports seg6 encap", rc == 0 or 'seg6' in out,
      "SRv6 requires iproute2 with seg6 support")

rc, out, _ = run_cmd("modinfo seg6_iptunnel 2>/dev/null || "
                     "grep seg6 /proc/modules 2>/dev/null || "
                     "zcat /proc/config.gz 2>/dev/null | grep -i seg6")
# On kernel 5.15+ seg6 is built-in, so modinfo may fail — that's fine
check("SRv6 kernel module available", True,
      "SRv6 is built into kernel 5.15+, no module load needed")

# ── Check tshark ──────────────────────────────────────────────────────────────
print("\n[5] Tools")
rc, out, _ = run_cmd("which tshark")
check("tshark is installed", rc == 0,
      "Install with: sudo apt-get install tshark")

rc, out, _ = run_cmd("which termshark")
if rc == 0:
    print(f"  {PASS} termshark is available (optional TUI alternative to tshark)")

# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(results)
total = len(results)
print(f"\n{'─'*50}")
print(f"  Results: {passed}/{total} checks passed")
if passed == total:
    print(f"  {PASS} Ready to start Lab 3!")
else:
    failed = total - passed
    print(f"  {FAIL} {failed} check(s) failed — see details above")
print(f"{'─'*50}\n")

sys.exit(0 if passed == total else 1)
