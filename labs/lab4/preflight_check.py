#!/usr/bin/env python3
"""
preflight_check.py — Lab 4
──────────────────────────
Checks that the revised Lab 4 environment is ready.

Usage:
    python3 preflight_check.py
"""

import subprocess
import sys
from pathlib import Path

import requests


PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

results = []


def check(name, passed, detail=""):
    status = PASS if passed else FAIL
    print(f"  {status} {name}")
    if detail:
        print(f"      {detail}")
    results.append(passed)
    return passed


def run_cmd(cmd):
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


print("=" * 52)
print("  Lab 4 — Preflight Check")
print("=" * 52)

print("\n[1] ONOS")
try:
    response = requests.get(
        "http://localhost:8181/onos/v1/devices",
        auth=("onos", "rocks"),
        timeout=5,
    )
    check("ONOS REST API reachable", response.status_code == 200, "Start ONOS: docker start onos")
    devices = response.json().get("devices", [])
    active = [device for device in devices if device.get("available")]
    check("Three transport nodes discovered", len(active) >= 3, f"Found {len(active)} active device(s). Run pingall in Mininet.")
except Exception as exc:
    check("ONOS REST API reachable", False, str(exc))
    check("Three transport nodes discovered", False, "ONOS not reachable")

print("\n[2] Mininet and topology")
rc, _, _ = run_cmd("pgrep -f 'mininet:h1'")
check("Mininet is running", rc == 0, "Start: sudo python3 lab4_topology.py")

rc, bridges, _ = run_cmd("sudo ovs-vsctl list-br")
check("r1, r2, and r3 exist", all(name in bridges for name in ["r1", "r2", "r3"]), f"Found bridges: {bridges.splitlines()}")

for host in ["h1", "h2", "h3", "mb1", "mb2", "mb3"]:
    rc, _, _ = run_cmd(f"pgrep -f 'mininet:{host}'")
    check(f"{host} namespace exists", rc == 0)

print("\n[3] SRv6")
rc, out, _ = run_cmd(
    "sudo mnexec -a $(pgrep -f 'mininet:h1' | head -1) "
    "sysctl net.ipv6.conf.all.seg6_enabled"
)
check("SRv6 enabled on h1", "seg6_enabled = 1" in out, "lab4_topology.py should configure this automatically")

rc, out, _ = run_cmd(
    "sudo mnexec -a $(pgrep -f 'mininet:h1' | head -1) "
    "ip -6 addr show"
)
check("SID assigned on h1", "fc00::1" in out, "lab4_topology.py should assign SIDs automatically")

print("\n[4] Middlebox services")
for middlebox, output_file in [
    ("mb1", "/tmp/mb_monitor.json"),
    ("mb2", "/tmp/mb_firewall.json"),
    ("mb3", "/tmp/mb_logger.json"),
]:
    check(
        f"{middlebox} service running ({output_file})",
        Path(output_file).exists(),
        "lab4_topology.py should start this automatically",
    )

print("\n[5] Tools")
for tool in ["tshark"]:
    rc, _, _ = run_cmd(f"which {tool}")
    check(f"{tool} installed", rc == 0, f"Install: sudo apt-get install {tool}")

rc, _, _ = run_cmd("python3 -c 'import requests'")
check("Python requests library available", rc == 0, "Install: pip3 install requests --break-system-packages")

print("\n[6] Services on h2")
rc, out, _ = run_cmd(
    "sudo mnexec -a $(pgrep -f 'mininet:h2' | head -1) "
    "curl -s -o /dev/null -w '%{http_code}' --max-time 2 http://10.0.0.2:80"
)
check("HTTP server on h2 port 80", out in ("200", "301", "404"), "lab4_topology.py should start this automatically")

rc, out, _ = run_cmd(
    "sudo mnexec -a $(pgrep -f 'mininet:h2' | head -1) "
    "curl -s -o /dev/null -w '%{http_code}' --max-time 2 http://10.0.0.2:8080"
)
check("HTTP server on h2 port 8080", out in ("200", "301", "404"), "lab4_topology.py should start this automatically")

print("\n[7] UDP receivers")
for port in ["5004", "5005"]:
    rc, _, _ = run_cmd(
        "sudo mnexec -a $(pgrep -f 'mininet:h2' | head -1) "
        f"ss -lun | grep ':{port} '"
    )
    check(f"UDP receiver on h2 port {port}", rc == 0, "lab4_topology.py should start this automatically")

print(f"\n{'─' * 52}")
passed = sum(results)
total = len(results)
print(f"  Results: {passed}/{total} checks passed")
if passed == total:
    print(f"  {PASS} Ready for revised Lab 4!")
    print("\n  Next:")
    print("    ./enter_host.sh h1")
    print("    python3 sender.py --host 10.0.0.2 --port 5004 --rate 3 --duration 20 --label primary")
    print("    ./enter_host.sh h3")
    print("    python3 sender.py --host 10.0.0.2 --port 5005 --rate 3 --duration 20 --label secondary")
    print("    python3 slice_controller_v2.py list-mbs")
else:
    print(f"  {FAIL} {total - passed} check(s) failed — see details above")
print(f"{'─' * 52}\n")

sys.exit(0 if passed == total else 1)
