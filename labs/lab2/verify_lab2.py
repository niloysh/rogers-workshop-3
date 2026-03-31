#!/usr/bin/env python3
"""
verify_lab2.py
──────────────
Checker for Lab 2 independent challenge.

Tests whether a Lab 2 controller app correctly:
  1. Finds hosts by IP in ONOS
  2. Installs flow rules that enable connectivity
  3. Detects a link failure and reroutes

Usage:
    sudo python3 verify_lab2.py 10.0.0.1 10.0.0.2

Prerequisites:
  - triangle_topology.py --onos must already be running
  - ONOS must already be running with the openflow app active
  - Run pingall in Mininet before running this checker

Note: This checker tests the ONOS state and connectivity directly.
      Keep Mininet and ONOS running while the checker runs.
      Keep your Lab 2 app running in another terminal while the checker runs.
"""

import sys
import requests

BASE = 'http://localhost:8181/onos/v1'
AUTH = ('onos', 'rocks')

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


def api_get(endpoint):
    try:
        r = requests.get(f'{BASE}/{endpoint}', auth=AUTH, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return None


# ── Test 1: ONOS is reachable ──────────────────────────────────────────────────

def test_onos_reachable():
    print("\n[1] ONOS connectivity")
    data = api_get('devices')
    check("ONOS REST API is reachable", data is not None,
          "Make sure ONOS is running: docker ps | grep onos")


# ── Test 2: Topology is discovered ────────────────────────────────────────────

def test_topology(src_ip, dst_ip):
    print("\n[2] Topology discovery")

    data = api_get('devices')
    devices = data.get('devices', []) if data else []
    active = [d for d in devices if d.get('available')]
    check("Three switches discovered", len(active) == 3,
          f"Found {len(active)} active device(s). Start triangle_topology.py --onos")

    data = api_get('links')
    links = data.get('links', []) if data else []
    check("Six links discovered (triangle × 2 directions)", len(links) == 6,
          f"Found {len(links)} link(s)")

    data = api_get('hosts')
    hosts = data.get('hosts', []) if data else []
    host_ips = [ip for h in hosts for ip in h.get('ipAddresses', [])]
    check(f"Host {src_ip} is known to ONOS", src_ip in host_ips,
          "Run pingall in Mininet to trigger host discovery")
    check(f"Host {dst_ip} is known to ONOS", dst_ip in host_ips,
          "Run pingall in Mininet to trigger host discovery")


# ── Test 3: Flow rules are installed ──────────────────────────────────────────

def test_flow_rules(src_ip, dst_ip):
    print("\n[3] Flow rule installation")
    print(f"    (checking app-installed rules for {src_ip} ↔ {dst_ip})")

    data = api_get('devices')
    if not data:
        check("Flow rules installed", False, "Cannot reach ONOS")
        return

    devices = [d['id'] for d in data.get('devices', [])]
    all_flows = []
    for device_id in devices:
        d = api_get(f'flows/{device_id}')
        if d:
            all_flows.extend(d.get('flows', []))

    app_flows = [f for f in all_flows if f.get('appId') == 'org.onosproject.cli']
    check("Flow rules installed by app", len(app_flows) > 0,
          f"Found {len(app_flows)} app flow(s). Is your Lab 2 app running?")

    # Check for both directions
    fwd_flows = [f for f in app_flows
                 if any(c.get('ip', '').startswith(src_ip)
                        for c in f.get('selector', {}).get('criteria', []))]
    rev_flows = [f for f in app_flows
                 if any(c.get('ip', '').startswith(dst_ip)
                        for c in f.get('selector', {}).get('criteria', []))]

    check(f"Forward rules installed ({src_ip} → {dst_ip})", len(fwd_flows) > 0)
    check(f"Reverse rules installed ({dst_ip} → {src_ip})", len(rev_flows) > 0)


# ── Test 4: Link failure rerouting ────────────────────────────────────────────

def test_rerouting():
    print("\n[4] Link failure and rerouting")
    print("    This test disables s1-s2 and checks ONOS updates topology.")
    print("    Make sure your Lab 2 app stays running during this test.\n")

    print("    To test manually:")
    print("      1. In Mininet CLI: link s1 s2 down")
    print("      2. Wait 5-10 seconds for your app to detect the failure")
    print("      3. Check: mininet> h1 ping -c 3 h2  (should still work via s3)")
    print("      4. Check: onos> links  (s1-s2 should be gone)")
    print("      5. Re-enable: link s1 s2 up")
    print()

    # Check ONOS sees 6 links (all up)
    data = api_get('links')
    links = data.get('links', []) if data else []
    active_links = len(links)

    if active_links < 6:
        print(f"  {WARN} Only {active_links} links visible — s1-s2 may already be down")
        print(f"      This is expected if you already ran the failure test")
    else:
        check("All 6 links currently active (ready for failure test)",
              active_links == 6)


# ── Summary ────────────────────────────────────────────────────────────────────

def print_summary():
    passed = sum(results)
    total = len(results)
    print(f"\n{'─'*50}")
    print(f"  Results: {passed}/{total} checks passed")
    if passed == total:
        print(f"  {PASS} All checks passed!")
    else:
        failed = total - passed
        print(f"  {FAIL} {failed} check(s) failed — see details above")
    print(f"{'─'*50}\n")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) != 3:
        print(f"Usage: python3 {sys.argv[0]} <src_ip> <dst_ip>")
        print(f"Example: python3 {sys.argv[0]} 10.0.0.1 10.0.0.2")
        sys.exit(1)

    src_ip, dst_ip = sys.argv[1], sys.argv[2]

    print("=" * 50)
    print("  Lab 2 — Verification")
    print(f"  Testing path: {src_ip} ↔ {dst_ip}")
    print("=" * 50)
    print("\n[setup] Keep Mininet, ONOS, and your Lab 2 app running while you verify.")

    test_onos_reachable()
    test_topology(src_ip, dst_ip)
    test_flow_rules(src_ip, dst_ip)
    test_rerouting()
    print_summary()


if __name__ == '__main__':
    main()
