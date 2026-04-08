#!/usr/bin/env python3
"""
verify_lab4.py
──────────────
Checker for the revised Lab 4 independent challenge.

Requirements checked:
  Slice 1 — premium monitored video
    - exists for h1 -> h2
    - uses low-latency intent
    - includes mb1 in the chain
    - bandwidth >= 4 Mbps
    - monitor output exists

  Slice 2 — secured and logged web access
    - exists for h3 -> h2
    - uses best-effort intent
    - includes mb2 and mb3 in the chain
    - bandwidth >= 2 Mbps
    - port 80 works from h3
    - port 8080 is blocked from h3

  Combined constraints
    - total reserved bandwidth <= 90 Mbps
    - slices use different endpoint pairs
"""

import json
import subprocess
import sys
from pathlib import Path


PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
STATE_FILE = "/tmp/slice_controller_state.json"
results = []


def check(name, passed, detail=""):
    status = PASS if passed else FAIL
    print(f"  {status} {name}")
    if detail:
        print(f"      {detail}")
    results.append(passed)
    return passed


def load_state():
    try:
        return json.loads(Path(STATE_FILE).read_text())
    except Exception:
        return {"slices": {}}


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return None


def mn_run(host, cmd, timeout=10):
    try:
        result = subprocess.run(
            f"sudo mnexec -a $(pgrep -f 'mininet:{host}' | head -1) {cmd}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


print("=" * 58)
print("  Lab 4 — Verification")
print("  Checking revised transport-slice requirements")
print("=" * 58)

state = load_state()
slices = state.get("slices", {})

print("\n[1] Slices provisioned")
check("At least two slices are active", len(slices) >= 2, f"Found {len(slices)} slice(s). Provision both services first.")
if len(slices) < 2:
    sys.exit(1)

video_slice = None
web_slice = None
for name, slice_data in slices.items():
    if slice_data["src"] == "h1" and slice_data["dst"] == "h2":
        video_slice = dict(slice_data, _name=name)
    if slice_data["src"] == "h3" and slice_data["dst"] == "h2":
        web_slice = dict(slice_data, _name=name)

print("\n[2] Slice 1 — Premium monitored video")
check("Video slice exists (h1 -> h2)", video_slice is not None, "Provision a slice for --src h1 --dst h2")
if video_slice:
    check("Video slice uses low-latency intent", video_slice.get("intent") == "low-latency", f"Found intent: {video_slice.get('intent')}")
    check("Video slice includes mb1", "mb1" in video_slice.get("chain", []), f"Found chain: {video_slice.get('chain')}")
    check("Video slice bandwidth >= 4 Mbps", video_slice.get("bandwidth", 0) >= 4, f"Found: {video_slice.get('bandwidth')} Mbps")
    monitor_data = load_json("/tmp/mb_monitor.json")
    monitor_ok = bool(monitor_data and isinstance(monitor_data.get("slices"), list))
    check("Monitor output exists", monitor_ok, "Inspect /tmp/mb_monitor.json and ensure mb1 is in the chain")

print("\n[3] Slice 2 — Secured and logged web access")
check("Web slice exists (h3 -> h2)", web_slice is not None, "Provision a slice for --src h3 --dst h2")
if web_slice:
    check("Web slice uses best-effort intent", web_slice.get("intent") == "best-effort", f"Found intent: {web_slice.get('intent')}")
    web_chain = set(web_slice.get("chain", []))
    check("Web slice includes mb2", "mb2" in web_chain, f"Found chain: {web_slice.get('chain')}")
    check("Web slice includes mb3", "mb3" in web_chain, f"Found chain: {web_slice.get('chain')}")
    check("Web slice bandwidth >= 2 Mbps", web_slice.get("bandwidth", 0) >= 2, f"Found: {web_slice.get('bandwidth')} Mbps")
    check("Web slice blocks port 8080", 8080 in web_slice.get("blocked_ports", []), f"Blocked ports: {web_slice.get('blocked_ports', [])}")

    print("\n  Testing HTTP behavior from h3...")
    rc, out, _ = mn_run(
        "h3",
        "curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://10.0.0.2:80",
        timeout=8,
    )
    check("Port 80 is accessible from h3", rc == 0 and out in ("200", "301", "404"), f"curl returned rc={rc}, code={out}")

    rc, out, _ = mn_run(
        "h3",
        "curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://10.0.0.2:8080",
        timeout=8,
    )
    blocked = rc != 0 or out not in ("200", "301", "404")
    check("Port 8080 is blocked from h3", blocked, f"curl returned rc={rc}, code={out}")

    firewall_data = load_json("/tmp/mb_firewall.json")
    logger_data = load_json("/tmp/mb_logger.json")
    check("Firewall policy file exists", firewall_data is not None, "Inspect /tmp/mb_firewall.json")
    check("Logger output file exists", logger_data is not None, "Inspect /tmp/mb_logger.json")

print("\n[4] Combined constraints")
total_bw = sum(slice_data.get("bandwidth", 0) for slice_data in slices.values())
check("Total bandwidth <= 90 Mbps", total_bw <= 90, f"Total reserved: {total_bw} Mbps")
if video_slice and web_slice:
    check(
        "Slices use different endpoint pairs",
        (video_slice["src"], video_slice["dst"]) != (web_slice["src"], web_slice["dst"]),
        "Workshop simplification requires unique endpoint pairs",
    )

passed = sum(results)
total = len(results)
print(f"\n{'─' * 58}")
print(f"  Results: {passed}/{total} checks passed")
if passed == total:
    print(f"  {PASS} All revised Lab 4 checks passed!")
else:
    print(f"  {FAIL} {total - passed} check(s) failed — see details above")
    print("      Reference: lab4_solution.py")
print(f"{'─' * 58}\n")

sys.exit(0 if passed == total else 1)
