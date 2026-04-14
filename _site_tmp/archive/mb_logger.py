#!/usr/bin/env python3
"""
mb_logger.py
────────────
Flow logger middlebox for Lab 4.

Logs all IP flows passing through this node.
Writes structured output to /tmp/mb_logger.json.

Run automatically by lab4_topology.py — do not start manually.
"""

import json
import threading
from datetime import datetime
from collections import defaultdict

try:
    from scapy.all import sniff, IP, IPv6, TCP, UDP
except ImportError:
    print("[mb_logger] Error: scapy not installed.")
    import sys
    sys.exit(1)

OUTPUT_FILE = '/tmp/mb_logger.json'

flows = []
flow_counts = defaultdict(int)
lock = threading.Lock()


def log_packet(pkt):
    if not (pkt.haslayer(IP) or pkt.haslayer(IPv6)):
        return

    if pkt.haslayer(IP):
        src = pkt[IP].src
        dst = pkt[IP].dst
    else:
        src = pkt[IPv6].src
        dst = pkt[IPv6].dst
    proto = 'tcp' if pkt.haslayer(TCP) else 'udp' if pkt.haslayer(UDP) else 'other'
    timestamp = datetime.now().strftime('%H:%M:%S')
    flow_key = f"{src}→{dst}/{proto}"

    with lock:
        flow_counts[flow_key] += 1

        # Only log new flows or every 100th packet
        if flow_counts[flow_key] == 1 or flow_counts[flow_key] % 100 == 0:
            entry = {
                'timestamp': timestamp,
                'src': src,
                'dst': dst,
                'proto': proto,
                'packet_count': flow_counts[flow_key],
            }
            flows.append(entry)
            print(f"[{timestamp}] [mb_logger] {src} → {dst} "
                  f"({proto}) packets: {flow_counts[flow_key]}")

            with open(OUTPUT_FILE, 'w') as f:
                json.dump({
                    'flows': flows,
                    'flow_summary': dict(flow_counts),
                    'total_flows': len(flow_counts),
                }, f, indent=2)


def main():
    print("[mb_logger] Starting on mb3-eth0")
    print(f"[mb_logger] Output file: {OUTPUT_FILE}")
    print("[mb_logger] Logging all flows...\n")

    with open(OUTPUT_FILE, 'w') as f:
        json.dump({'flows': [], 'flow_summary': {}, 'total_flows': 0}, f)

    try:
        sniff(iface='mb3-eth0', prn=log_packet, store=0)
    except KeyboardInterrupt:
        print("\n[mb_logger] Stopped.")


if __name__ == '__main__':
    main()
