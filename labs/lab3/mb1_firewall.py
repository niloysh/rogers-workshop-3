#!/usr/bin/env python3
"""
mb1_firewall.py
───────────────
Simplistic firewall for mb1.

Run this from a regular shell:
    ./run_mb1_firewall.sh

Policy:
    ALLOW  TCP port 80 (HTTP) — legitimate web traffic
    BLOCK  everything else    — ICMP, other TCP, UDP

Uses ip6tables FORWARD chain since mb1 is filtering IPv6 traffic
steered through it by SRv6.
"""

import subprocess
import sys
import time


def flush_rules():
    subprocess.run(['ip6tables', '-F', 'FORWARD'], check=True)
    subprocess.run(['ip6tables', '-F', 'INPUT'],   check=True)


def install_rules():
    # Default policy: drop forwarded traffic
    subprocess.run(['ip6tables', '-P', 'FORWARD', 'DROP'], check=True)

    # Allow HTTP (port 80) in both directions
    subprocess.run([
        'ip6tables', '-A', 'FORWARD',
        '-p', 'tcp', '--dport', '80',
        '-j', 'ACCEPT'
    ], check=True)

    subprocess.run([
        'ip6tables', '-A', 'FORWARD',
        '-p', 'tcp', '--sport', '80',
        '-j', 'ACCEPT'
    ], check=True)

    # Allow established/related connections
    subprocess.run([
        'ip6tables', '-A', 'FORWARD',
        '-m', 'state', '--state', 'ESTABLISHED,RELATED',
        '-j', 'ACCEPT'
    ], check=True)


def show_rules():
    print("\n[mb1 firewall] Active rules:")
    print(get_forward_rules())


def get_forward_rules(with_line_numbers=False):
    cmd = ['ip6tables', '-L', 'FORWARD', '-v', '-n']
    if with_line_numbers:
        cmd.append('--line-numbers')

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def render_status():
    rules = get_forward_rules(with_line_numbers=True)

    # Redraw the terminal in place so we do not spam the same table repeatedly.
    print("\033[2J\033[H", end="")
    print("[mb1 firewall] Running")
    print("[mb1 firewall] Policy: ALLOW IPv6 HTTP, BLOCK all other forwarded IPv6 traffic")
    print("[mb1 firewall] Press Ctrl+C to stop and flush rules.\n")
    print(rules)
    sys.stdout.flush()


def main():
    print("[mb1 firewall] Starting...")
    flush_rules()
    install_rules()
    show_rules()

    try:
        last_rules = None
        while True:
            current_rules = get_forward_rules(with_line_numbers=True)
            if current_rules != last_rules:
                render_status()
                last_rules = current_rules
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n[mb1 firewall] Stopping — flushing rules...")
        flush_rules()
        subprocess.run(['ip6tables', '-P', 'FORWARD', 'ACCEPT'], check=True)
        print("[mb1 firewall] Rules flushed.")


if __name__ == '__main__':
    main()
