#!/usr/bin/env python3
"""
lab2_skeleton.py
────────────────
Independent challenge — Lab 2

A controller application that:
  1. Takes two host IPs as command-line arguments
  2. Finds the host IDs in ONOS
  3. Computes the shortest path using the ONOS REST API
  4. Installs flow rules on each switch along the path
  5. Monitors port status every 5 seconds
  6. On link failure, removes old rules and reinstalls on new path

Suggested implementation order:
  1. finish find_host_by_ip()
  2. finish get_path()
  3. finish install_flow_rules()
  4. finish remove_flow_rules()
  5. finish detect_failure()

Usage:
    python3 lab2_skeleton.py 10.0.0.1 10.0.0.2

Before running:
    - triangle_topology.py --onos must be running
    - ONOS must have discovered hosts (run pingall from Mininet first)
    - The OpenFlow app must be active in ONOS
"""

import sys
import time
import requests

# ── ONOS REST API ──────────────────────────────────────────────────────────────
BASE = 'http://localhost:8181/onos/v1'
AUTH = ('onos', 'rocks')
APP_ID = 'org.onosproject.cli'   # tag our rules so we can find and remove them

# Polling interval for link failure detection (seconds)
POLL_INTERVAL = 5


# ── Helper ─────────────────────────────────────────────────────────────────────

def api_get(endpoint):
    """GET from ONOS REST API. Returns parsed JSON."""
    r = requests.get(f'{BASE}/{endpoint}', auth=AUTH)
    r.raise_for_status()
    return r.json()

def api_post(endpoint, data):
    """POST to ONOS REST API. Returns response.

    Hint: treat HTTP 200/201 as success. Do not assume the response body
    contains JSON with a flow ID.
    """
    r = requests.post(f'{BASE}/{endpoint}', json=data, auth=AUTH)
    return r

def api_delete(endpoint):
    """DELETE from ONOS REST API. Returns response."""
    r = requests.delete(f'{BASE}/{endpoint}', auth=AUTH)
    return r


# ── Step 1: Find hosts ─────────────────────────────────────────────────────────

def get_hosts():
    """Return all hosts known to ONOS."""
    return api_get('hosts')['hosts']

def find_host_by_ip(ip):
    """
    Find a host ID by its IP address.

    TODO: query get_hosts() and return the 'id' of the host whose
    'ipAddresses' list contains the given ip string.
    Return None if not found.
    """
    # TODO
    pass


# ── Step 2: Get path ───────────────────────────────────────────────────────────

def get_path(src_host_id, dst_host_id):
    """
    Get the shortest path between two hosts.

    ONOS endpoint: GET /paths/<srcId>/<dstId>
    Returns a list of path objects. Each path has a 'links' array.
    Each link has: src.device, src.port, dst.device, dst.port

    TODO: call the paths endpoint and return the first path's links list.
    Return None if no path exists.

    Hint: host IDs and device IDs are different.
          You need to find which device each host is connected to first.
          Check GET /hosts — each host has a 'locations' list with
          'elementId' and 'port' fields.
          Then query /paths/<srcDevice>/<dstDevice>, not /paths/<srcHost>/<dstHost>.
    """
    # TODO
    pass


# ── Step 3: Install flow rules ─────────────────────────────────────────────────

def build_flow_rule(src_ip, dst_ip, out_port, priority=40000):
    """
    Build an ONOS flow rule JSON object.

    This matches IP traffic from src_ip to dst_ip and forwards out out_port.
    The appId field lets us identify and remove our rules later.
    """
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

    TODO: for each link in path_links:
      - install a forward rule on link['src']['device']
        matching src_ip->dst_ip, outputting on link['src']['port']
      - install a reverse rule on link['dst']['device']
        matching dst_ip->src_ip, outputting on link['dst']['port']

    Use build_flow_rule() to construct each rule.
    Use api_post('flows/<deviceId>', rule) to install it.

    Hint: path_links gives you one direction. Make sure you handle
    both forward (src->dst) and reverse (dst->src) rules.
    """
    # TODO
    pass


# ── Step 4: Remove flow rules ──────────────────────────────────────────────────

def remove_flow_rules(devices):
    """
    Remove all flow rules installed by this app.

    TODO: for each device in devices:
      - GET /flows/<deviceId>
      - filter flows where appId matches APP_ID
      - DELETE /flows/<deviceId>/<flowId> for each matching flow

    Hint: flow objects from /flows/<deviceId> use 'id' as the flow ID field.
    """
    # TODO
    pass


# ── Step 5: Monitor and reroute ────────────────────────────────────────────────

def get_port_status(device_id):
    """Return list of ports for a device, each with 'isEnabled' field."""
    return api_get(f'devices/{device_id}/ports')['ports']

def get_active_devices(path_links):
    """Return set of device IDs involved in the current path."""
    devices = set()
    for link in path_links:
        devices.add(link['src']['device'])
        devices.add(link['dst']['device'])
    return devices

def detect_failure(path_links):
    """
    Check whether any link on the current path has gone down.

    TODO: for each link in path_links, check if the src port on src device
    is still enabled. Return True if a failure is detected, False otherwise.

    Use get_port_status(device_id) and check 'isEnabled' on the relevant port.
    """
    # TODO
    return False

def monitor_and_reroute(src_ip, dst_ip, src_host_id, dst_host_id):
    """
    Main monitoring loop.

    - Install initial path
    - Every POLL_INTERVAL seconds, check for link failures
    - On failure: remove old rules, recompute path, install new rules
    """
    print(f"\n[monitor] Finding path from {src_ip} to {dst_ip}...")

    path_links = get_path(src_host_id, dst_host_id)
    if not path_links:
        print("[error] No path found. Make sure pingall has been run in Mininet.")
        return

    print(f"[monitor] Path has {len(path_links)} links. Installing rules...")
    install_flow_rules(path_links, src_ip, dst_ip)
    print(f"[monitor] Rules installed. Monitoring every {POLL_INTERVAL}s...")

    while True:
        time.sleep(POLL_INTERVAL)

        if detect_failure(path_links):
            print("[monitor] Link failure detected! Recomputing path...")

            devices = get_active_devices(path_links)
            remove_flow_rules(devices)

            # TODO: recompute the path, then reinstall rules for the new path
            path_links = get_path(src_host_id, dst_host_id)
            if path_links:
                install_flow_rules(path_links, src_ip, dst_ip)
                print(f"[monitor] Rerouted. New path has {len(path_links)} links.")
            else:
                print("[monitor] No alternate path available.")
        else:
            print(f"[monitor] Path OK ({len(path_links)} links active)")


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
        print(f"[error] Host {src_ip} not found in ONOS. Run pingall in Mininet first.")
        sys.exit(1)
    if not dst_host_id:
        print(f"[error] Host {dst_ip} not found in ONOS. Run pingall in Mininet first.")
        sys.exit(1)

    print(f"[init] src: {src_host_id}")
    print(f"[init] dst: {dst_host_id}")

    try:
        monitor_and_reroute(src_ip, dst_ip, src_host_id, dst_host_id)
    except KeyboardInterrupt:
        print("\n[exit] Stopping monitor.")


if __name__ == '__main__':
    main()
