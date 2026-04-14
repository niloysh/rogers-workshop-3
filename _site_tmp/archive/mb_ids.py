#!/usr/bin/env python3
"""
mb_ids.py
─────────
HTTP Intrusion Detection System middlebox for Lab 4.

Passively inspects HTTP traffic passing through.
Alerts on suspicious URL patterns.
Writes structured output to /tmp/mb_ids.json.

Run automatically by lab4_topology.py — do not start manually.
"""

import json
import threading
from datetime import datetime
from collections import defaultdict

try:
    from scapy.all import sniff, IP, TCP, Raw
except ImportError:
    print("[mb_ids] Error: scapy not installed.")
    import sys
    sys.exit(1)

OUTPUT_FILE = '/tmp/mb_ids.json'

SUSPICIOUS_PATTERNS = [
    '/malware', '/exploit', '/shell',
    '/admin', '/passwd', '/etc/passwd',
    'cmd=', 'exec(',
]

alerts = []
ok_count = 0
lock = threading.Lock()


def inspect(pkt):
    global ok_count
    if not (pkt.haslayer(IP) and pkt.haslayer(TCP) and pkt.haslayer(Raw)):
        return
    if pkt[TCP].dport != 80 and pkt[TCP].sport != 80:
        return
    try:
        payload = pkt[Raw].load.decode('utf-8', errors='ignore')
    except Exception:
        return
    if not payload.startswith(('GET ', 'POST ', 'PUT ', 'DELETE ')):
        return

    src_ip = pkt[IP].src
    dst_ip = pkt[IP].dst
    request_line = payload.split('\r\n')[0]
    timestamp = datetime.now().strftime('%H:%M:%S')
    is_suspicious = any(p in payload.lower() for p in SUSPICIOUS_PATTERNS)

    with lock:
        if is_suspicious:
            alert = {
                'timestamp': timestamp,
                'src': src_ip,
                'dst': dst_ip,
                'request': request_line,
                'severity': 'high',
            }
            alerts.append(alert)
            print(f"[{timestamp}] [mb_ids] \033[91m[ALERT]\033[0m "
                  f"{src_ip} → {dst_ip} — {request_line}")
        else:
            ok_count += 1
            print(f"[{timestamp}] [mb_ids] \033[92m[OK]\033[0m "
                  f"{src_ip} → {dst_ip} — {request_line}")

        with open(OUTPUT_FILE, 'w') as f:
            json.dump({
                'alerts': alerts,
                'ok_count': ok_count,
                'total_inspected': len(alerts) + ok_count,
            }, f, indent=2)


def main():
    print("[mb_ids] Starting on mb3-eth0")
    print(f"[mb_ids] Output file: {OUTPUT_FILE}")
    print("[mb_ids] Monitoring HTTP traffic...\n")

    with open(OUTPUT_FILE, 'w') as f:
        json.dump({'alerts': [], 'ok_count': 0, 'total_inspected': 0}, f)

    try:
        sniff(iface='mb3-eth0', filter='tcp port 80',
              prn=inspect, store=0)
    except KeyboardInterrupt:
        print("\n[mb_ids] Stopped.")


if __name__ == '__main__':
    main()