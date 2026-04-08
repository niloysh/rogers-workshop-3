#!/usr/bin/env python3
"""
mb_firewall.py
──────────────
Port-based firewall middlebox for Lab 4.

Enforces port-based access control on forwarded traffic.
Blocked ports are configured via /tmp/mb_firewall_config.json
written by the slice controller.
Writes structured output to /tmp/mb_firewall.json.

Run automatically by lab4_topology.py — do not start manually.
"""

import json
import time
import subprocess
import threading
from datetime import datetime
from collections import defaultdict

OUTPUT_FILE = '/tmp/mb_firewall.json'
CONFIG_FILE = '/tmp/mb_firewall_config.json'

blocked_ports = set()
allowed_connections = []
blocked_connections = []
lock = threading.Lock()


def load_config():
    """Load firewall config written by slice controller."""
    global blocked_ports
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        new_blocked = set(config.get('blocked_ports', []))
        if new_blocked != blocked_ports:
            blocked_ports = new_blocked
            apply_iptables_rules()
            print(f"[mb_firewall] Config updated — blocked ports: {blocked_ports}")
    except (FileNotFoundError, json.JSONDecodeError):
        pass


def apply_iptables_rules():
    """Apply iptables rules based on current config."""
    # Flush existing rules
    subprocess.run(['iptables', '-F', 'FORWARD'], check=False)
    subprocess.run(['iptables', '-P', 'FORWARD', 'ACCEPT'], check=False)

    # Block configured ports
    for port in blocked_ports:
        subprocess.run([
            'iptables', '-A', 'FORWARD',
            '-p', 'tcp', '--dport', str(port),
            '-j', 'DROP'
        ], check=False)
        subprocess.run([
            'iptables', '-A', 'FORWARD',
            '-p', 'tcp', '--sport', str(port),
            '-j', 'DROP'
        ], check=False)
        print(f"[mb_firewall] Blocking port {port}")


def monitor_connections():
    """Monitor iptables counters and write JSON report."""
    while True:
        time.sleep(5)
        load_config()

        timestamp = datetime.now().strftime('%H:%M:%S')

        # Read iptables counters
        result = subprocess.run(
            ['iptables', '-L', 'FORWARD', '-v', '-n', '--line-numbers'],
            capture_output=True, text=True
        )

        blocked = []
        allowed = []
        for line in result.stdout.splitlines():
            if 'DROP' in line and 'dpt:' in line:
                port = line.split('dpt:')[-1].strip().split()[0]
                blocked.append({
                    'port': int(port),
                    'proto': 'tcp',
                    'action': 'DROP',
                    'timestamp': timestamp,
                })
            elif 'ACCEPT' in line:
                allowed.append({
                    'action': 'ACCEPT',
                    'timestamp': timestamp,
                })

        report = {
            'timestamp': timestamp,
            'blocked_ports': list(blocked_ports),
            'blocked_connections': blocked,
            'allowed_connections': allowed,
        }

        with open(OUTPUT_FILE, 'w') as f:
            json.dump(report, f, indent=2)

        if blocked_ports:
            print(f"[{timestamp}] [mb_firewall] Active — "
                  f"blocking ports: {blocked_ports}")


def main():
    print("[mb_firewall] Starting...")
    print(f"[mb_firewall] Config file: {CONFIG_FILE}")
    print(f"[mb_firewall] Output file: {OUTPUT_FILE}")
    print("[mb_firewall] Waiting for configuration from slice controller...\n")

    # Enable IP forwarding
    subprocess.run(['sysctl', '-w', 'net.ipv4.ip_forward=1'], check=False)

    # Write empty report
    with open(OUTPUT_FILE, 'w') as f:
        json.dump({
            'timestamp': None,
            'blocked_ports': [],
            'blocked_connections': [],
            'allowed_connections': [],
        }, f)

    # Start monitor thread
    t = threading.Thread(target=monitor_connections, daemon=True)
    t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[mb_firewall] Stopping — flushing rules...")
        subprocess.run(['iptables', '-F', 'FORWARD'], check=False)
        subprocess.run(['iptables', '-P', 'FORWARD', 'ACCEPT'], check=False)


if __name__ == '__main__':
    main()