#!/usr/bin/env python3
"""
mb_monitor.py
─────────────
Per-slice throughput monitor for Lab 4.

Passively measures throughput of traffic passing through this node.
Reports per-slice Mbps and whether the SLA target is being met.
Writes structured output to /tmp/mb_monitor.json every 5 seconds.

Run automatically by lab4_topology.py — do not start manually.
"""

import json
import time
import threading
from datetime import datetime
from collections import defaultdict

try:
    from scapy.all import sniff, IP, IPv6, TCP, UDP
except ImportError:
    print("[mb_monitor] Error: scapy not installed.")
    import sys
    sys.exit(1)

OUTPUT_FILE = '/tmp/mb_monitor.json'
CONFIG_FILE = '/tmp/mb_monitor_config.json'
INTERVAL = 5  # seconds between reports

# Per-slice byte counters
byte_counts = defaultdict(int)
slice_registry = {}  # src_ip → slice name + sla
lock = threading.Lock()


def register_slice(src_ip, name, sla_mbps):
    """Called by slice controller to register a slice for monitoring."""
    with lock:
        slice_registry[src_ip] = {
            'name': name,
            'sla_mbps': sla_mbps,
        }


def load_config():
    """Load slice registrations written by the controller."""
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    if isinstance(config, dict) and 'src_ip' in config:
        with lock:
            slice_registry[config['src_ip']] = {
                'name': config['slice'],
                'sla_mbps': config['sla_mbps'],
            }


def count_packet(pkt):
    if pkt.haslayer(IP):
        src = pkt[IP].src
    elif pkt.haslayer(IPv6):
        src = pkt[IPv6].src
    else:
        return
    size = len(pkt)
    with lock:
        byte_counts[src] += size


def report():
    """Periodically compute throughput and write JSON report."""
    while True:
        time.sleep(INTERVAL)
        load_config()
        with lock:
            timestamp = datetime.now().strftime('%H:%M:%S')
            slices = []

            for src_ip, info in slice_registry.items():
                bytes_in_interval = byte_counts.get(src_ip, 0)
                throughput_mbps = round(
                    (bytes_in_interval * 8) / (INTERVAL * 1_000_000), 2
                )
                sla_mbps = info['sla_mbps']
                sla_met = throughput_mbps >= sla_mbps * 0.9  # 10% tolerance

                slice_data = {
                    'name': info['name'],
                    'src_ip': src_ip,
                    'throughput_mbps': throughput_mbps,
                    'sla_target_mbps': sla_mbps,
                    'sla_met': sla_met,
                    'timestamp': timestamp,
                }
                slices.append(slice_data)

                status = '\033[92m[OK]\033[0m' if sla_met else '\033[91m[VIOLATION]\033[0m'
                print(f"[{timestamp}] [mb_monitor] {status} "
                      f"{info['name']}: {throughput_mbps} Mbps "
                      f"(SLA: {sla_mbps} Mbps)")

            # Reset counters
            byte_counts.clear()

            # Write JSON report
            report_data = {
                'timestamp': timestamp,
                'interval_seconds': INTERVAL,
                'slices': slices,
            }
            with open(OUTPUT_FILE, 'w') as f:
                json.dump(report_data, f, indent=2)


def main():
    print(f"[mb_monitor] Starting on mb1-eth0")
    print(f"[mb_monitor] Writing reports to {OUTPUT_FILE}")
    print(f"[mb_monitor] Config file: {CONFIG_FILE}")
    print(f"[mb_monitor] Waiting for slice registrations...\n")

    # Write empty report immediately
    with open(OUTPUT_FILE, 'w') as f:
        json.dump({'timestamp': None, 'slices': []}, f)

    # Start reporting thread
    t = threading.Thread(target=report, daemon=True)
    t.start()

    # Sniff all traffic
    try:
        sniff(iface='mb1-eth0', prn=count_packet, store=0)
    except KeyboardInterrupt:
        print("\n[mb_monitor] Stopped.")


if __name__ == '__main__':
    main()
