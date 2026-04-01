#!/usr/bin/env python3
"""
mb2_ids.py
──────────
Simplistic IDS (Intrusion Detection System) for mb2.

Run this from a regular shell:
    ./run_mb2_ids.sh

Behaviour:
    - Passively sniffs IPv6 traffic passing through mb2
    - Inspects the request URL for suspicious patterns
    - Prints [ALERT] for suspicious requests, [OK] for normal ones
    - Traffic always passes through — IDS never blocks

Suspicious patterns detected:
    /malware, /exploit, /shell, /admin, /passwd, /etc/passwd

Note:
    The IDS only sees traffic if SRv6 is steering it through mb2.
    Without SRv6, traffic bypasses mb2 and nothing is logged.
"""

import sys
from datetime import datetime

try:
    from scapy.all import sniff, IP, IPv6, TCP, Raw
except ImportError:
    print("[mb2 IDS] Error: scapy not installed.")
    print("          Install with: pip3 install scapy --break-system-packages")
    sys.exit(1)


# Patterns that trigger an alert
SUSPICIOUS_PATTERNS = [
    '/malware',
    '/exploit',
    '/shell',
    '/admin',
    '/passwd',
    '/etc/passwd',
    'cmd=',
    'exec(',
]


def inspect_packet(pkt):
    if not (pkt.haslayer(TCP) and pkt.haslayer(Raw)):
        return

    # Only inspect HTTP traffic
    if pkt[TCP].dport != 80 and pkt[TCP].sport != 80:
        return

    try:
        payload = pkt[Raw].load.decode('utf-8', errors='ignore')
    except Exception:
        return

    # Only inspect HTTP requests (not responses)
    if not payload.startswith(('GET ', 'POST ', 'PUT ', 'DELETE ')):
        return

    if pkt.haslayer(IPv6):
        src_ip = pkt[IPv6].src
        dst_ip = pkt[IPv6].dst
    elif pkt.haslayer(IP):
        src_ip = pkt[IP].src
        dst_ip = pkt[IP].dst
    else:
        return

    # Extract the request line
    request_line = payload.split('\r\n')[0]
    timestamp = datetime.now().strftime('%H:%M:%S')

    # Check for suspicious patterns
    is_suspicious = any(p in payload.lower() for p in SUSPICIOUS_PATTERNS)

    if is_suspicious:
        print(f"[{timestamp}] [mb2 IDS] \033[91m[ALERT]\033[0m "
              f"{src_ip} → {dst_ip} — {request_line}")
        # Log to file as well
        with open('/tmp/mb2_ids.log', 'a') as f:
            f.write(f"[{timestamp}] ALERT {src_ip} → {dst_ip} {request_line}\n")
    else:
        print(f"[{timestamp}] [mb2 IDS] \033[92m[OK]\033[0m    "
              f"{src_ip} → {dst_ip} — {request_line}")
        with open('/tmp/mb2_ids.log', 'a') as f:
            f.write(f"[{timestamp}] OK    {src_ip} → {dst_ip} {request_line}\n")


def main():
    iface = 'mb2-eth0'

    print(f"[mb2 IDS] Starting on {iface}...")
    print(f"[mb2 IDS] Monitoring IPv6 traffic and inspecting HTTP requests")
    print(f"[mb2 IDS] Suspicious patterns: {', '.join(SUSPICIOUS_PATTERNS)}")
    print(f"[mb2 IDS] Log file: /tmp/mb2_ids.log")
    print(f"[mb2 IDS] Waiting for traffic... (traffic only appears if SRv6 is active)\n")

    # Clear log file
    open('/tmp/mb2_ids.log', 'w').close()

    try:
        sniff(
            iface=iface,
            # Keep the capture filter broad here. With SRH present, a narrower
            # BPF filter like "tcp port 80" may miss packets because TCP is no
            # longer the immediate next header after IPv6.
            filter='ip6',
            prn=inspect_packet,
            store=0
        )
    except KeyboardInterrupt:
        print("\n[mb2 IDS] Stopped.")
        print(f"[mb2 IDS] Log saved to /tmp/mb2_ids.log")


if __name__ == '__main__':
    main()
