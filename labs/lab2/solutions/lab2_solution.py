#!/usr/bin/env python3
"""
lab2_solution.py
────────────────
Reference solution — Lab 2 independent challenge.

Usage:
    python3 lab2_solution.py 10.0.0.1 10.0.0.2

Before running:
    - triangle_topology.py --onos must be running
    - ONOS must have discovered hosts (run pingall from Mininet first)
    - The OpenFlow app must be active in ONOS
"""

import sys
import time
import requests

BASE = 'http://localhost:8181/onos/v1'
AUTH = ('onos', 'rocks')
APP_ID = 'org.onosproject.cli'
POLL_INTERVAL = 5


# ── Helpers ────────────────────────────────────────────────────────────────────

def api_get(endpoint):
    r = requests.get(f'{BASE}/{endpoint}', auth=AUTH)
    r.raise_for_status()
    return r.json()

def api_post(endpoint, data):
    r = requests.post(f'{BASE}/{endpoint}', json=data, auth=AUTH)
    return r

def api_delete(endpoint):
    r = requests.delete(f'{BASE}/{endpoint}', auth=AUTH)
    return r


# ── Step 1: Find hosts ─────────────────────────────────────────────────────────

def get_hosts():
    return api_get('hosts')['hosts']

def find_host_by_ip(ip):
    for host in get_hosts():
        if ip in host['ipAddresses']:
            return host['id']
    return None

def get_host_location(host_id):
    """Return the device ID and port where this host is attached."""
    hosts = get_hosts()
    for h in hosts:
        if h['id'] == host_id:
            locations = h.get('locations', [])
            if locations:
                return locations[0]['elementId'], locations[0]['port']
    return None, None


# ── Step 2: Get path ───────────────────────────────────────────────────────────

def get_path(src_host_id, dst_host_id):
    """
    Get the shortest path between two hosts via their attached devices.
    Returns the links list of the first path, or None.
    """
    src_device, _ = get_host_location(src_host_id)
    dst_device, _ = get_host_location(dst_host_id)

    if not src_device or not dst_device:
        return None

    if src_device == dst_device:
        # hosts on same switch — no inter-switch links needed
        return []

    try:
        data = api_get(f'paths/{src_device}/{dst_device}')
        paths = data.get('paths', [])
        if not paths:
            return None
        return paths[0]['links']
    except Exception as e:
        print(f"[error] Failed to get path: {e}")
        return None


# ── Step 3: Install flow rules ─────────────────────────────────────────────────

def build_flow_rule(src_ip, dst_ip, out_port, priority=40000):
    return {
        "priority": priority,
        "timeout": 0,
        "isPermanent": True,
        "appId": APP_ID,
        "treatment": {
            "instructions": [
                {"type": "OUTPUT", "port": str(out_port)}
            ]
        },
        "selector": {
            "criteria": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IPV4_SRC", "ip": f"{src_ip}/32"},
                {"type": "IPV4_DST", "ip": f"{dst_ip}/32"}
            ]
        }
    }

def install_flow_rules(path_links, src_ip, dst_ip):
    """
    Install bidirectional flow rules on each switch along the path.

    For each link A→B:
      - on device A: match src_ip→dst_ip, output on A's port toward B
      - on device B: match dst_ip→src_ip, output on B's port toward A
    """
    for link in path_links:
        src_device = link['src']['device']
        src_port   = link['src']['port']
        dst_device = link['dst']['device']
        dst_port   = link['dst']['port']

        # Forward rule: src_ip → dst_ip, output toward dst
        fwd_rule = build_flow_rule(src_ip, dst_ip, src_port)
        r = api_post(f'flows/{src_device}', fwd_rule)
        if r.status_code in (200, 201):
            print(f"  [rule] {src_device} port {src_port}: {src_ip} → {dst_ip}")
        else:
            print(f"  [warning] Could not install rule on {src_device}: HTTP {r.status_code}")

        # Reverse rule: dst_ip → src_ip, output back toward src
        rev_rule = build_flow_rule(dst_ip, src_ip, dst_port)
        r = api_post(f'flows/{dst_device}', rev_rule)
        if r.status_code in (200, 201):
            print(f"  [rule] {dst_device} port {dst_port}: {dst_ip} → {src_ip}")
        else:
            print(f"  [warning] Could not install rule on {dst_device}: HTTP {r.status_code}")

    # Also install rules on edge switches connecting to hosts
    _install_edge_rules(path_links, src_ip, dst_ip)

def _install_edge_rules(path_links, src_ip, dst_ip):
    """Install rules on the first and last switch connecting to hosts."""
    # This handles the case where the host-facing port is not in path_links
    # (path_links only contains inter-switch links)
    if not path_links:
        return

    first_device = path_links[0]['src']['device']
    last_device  = path_links[-1]['dst']['device']

    # Find host-facing ports
    hosts = get_hosts()
    src_host_port = dst_host_port = None

    for h in hosts:
        locations = h.get('locations', [])
        if not locations:
            continue
        location = locations[0]
        if src_ip in h['ipAddresses'] and location['elementId'] == first_device:
            src_host_port = location['port']
        if dst_ip in h['ipAddresses'] and location['elementId'] == last_device:
            dst_host_port = location['port']

    if dst_host_port:
        rule = build_flow_rule(src_ip, dst_ip, dst_host_port)
        r = api_post(f'flows/{last_device}', rule)
        if r.status_code in (200, 201):
            print(f"  [rule] {last_device} port {dst_host_port}: {src_ip} → {dst_ip} (edge)")

    if src_host_port:
        rule = build_flow_rule(dst_ip, src_ip, src_host_port)
        r = api_post(f'flows/{first_device}', rule)
        if r.status_code in (200, 201):
            print(f"  [rule] {first_device} port {src_host_port}: {dst_ip} → {src_ip} (edge)")


# ── Step 4: Remove flow rules ──────────────────────────────────────────────────

def remove_flow_rules(devices):
    """Remove all flow rules installed by this app on the given devices."""
    for device_id in devices:
        try:
            flows = api_get(f'flows/{device_id}').get('flows', [])
            for flow in flows:
                if flow.get('appId') == APP_ID:
                    flow_id = flow['id']
                    api_delete(f'flows/{device_id}/{flow_id}')
                    print(f"  [remove] {device_id} flow {flow_id}")
        except Exception as e:
            print(f"  [warning] Could not remove rules from {device_id}: {e}")


# ── Step 5: Monitor and reroute ────────────────────────────────────────────────

def get_port_status(device_id):
    return api_get(f'devices/{device_id}/ports')['ports']

def get_active_devices(path_links):
    devices = set()
    for link in path_links:
        devices.add(link['src']['device'])
        devices.add(link['dst']['device'])
    return devices

def detect_failure(path_links):
    """Return True if any link on the current path has gone down."""
    for link in path_links:
        device_id = link['src']['device']
        port_num  = str(link['src']['port'])
        try:
            ports = get_port_status(device_id)
            for port in ports:
                if str(port['port']) == port_num and not port['isEnabled']:
                    print(f"  [failure] {device_id} port {port_num} is down")
                    return True
        except Exception as e:
            print(f"  [warning] Could not check port status: {e}")
    return False

def monitor_and_reroute(src_ip, dst_ip, src_host_id, dst_host_id):
    print(f"\n[monitor] Finding path from {src_ip} to {dst_ip}...")

    path_links = get_path(src_host_id, dst_host_id)
    if path_links is None:
        print("[error] No path found. Make sure pingall has been run in Mininet.")
        return

    print(f"[monitor] Path has {len(path_links)} inter-switch links. Installing rules...")
    install_flow_rules(path_links, src_ip, dst_ip)
    print(f"[monitor] Rules installed. Monitoring every {POLL_INTERVAL}s...\n")

    while True:
        time.sleep(POLL_INTERVAL)

        if detect_failure(path_links):
            print("[monitor] Link failure detected! Recomputing path...")

            devices = get_active_devices(path_links)
            # Add all devices (including edge) before removing
            all_devices = api_get('devices')['devices']
            all_device_ids = {d['id'] for d in all_devices}
            remove_flow_rules(all_device_ids)

            time.sleep(2)  # give ONOS time to update topology

            path_links = get_path(src_host_id, dst_host_id)
            if path_links is not None:
                install_flow_rules(path_links, src_ip, dst_ip)
                print(f"[monitor] Rerouted. New path has {len(path_links)} links.\n")
            else:
                print("[monitor] No alternate path available.\n")
        else:
            print(f"[monitor] Path OK ({len(path_links)} inter-switch links active)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) != 3:
        print(f"Usage: python3 {sys.argv[0]} <src_ip> <dst_ip>")
        sys.exit(1)

    src_ip, dst_ip = sys.argv[1], sys.argv[2]
    print(f"[init] Looking up hosts for {src_ip} and {dst_ip}...")

    src_host_id = find_host_by_ip(src_ip)
    dst_host_id = find_host_by_ip(dst_ip)

    if not src_host_id:
        print(f"[error] Host {src_ip} not found. Run pingall in Mininet first.")
        sys.exit(1)
    if not dst_host_id:
        print(f"[error] Host {dst_ip} not found. Run pingall in Mininet first.")
        sys.exit(1)

    print(f"[init] src: {src_host_id}")
    print(f"[init] dst: {dst_host_id}")

    try:
        monitor_and_reroute(src_ip, dst_ip, src_host_id, dst_host_id)
    except KeyboardInterrupt:
        print("\n[exit] Stopping monitor.")
        sys.exit(0)


if __name__ == '__main__':
    main()
