#!/usr/bin/env python3
"""
Shared helpers for Lab 4 interactive demos.
"""

import time


H1_PORT = 5201
H3_PORT = 5202
DEMO_HOSTS = ("h1", "h2", "h3", "mb1", "mb2")


def start_servers(h2):
    h2.cmd("pkill -f iperf3 2>/dev/null; true")
    time.sleep(0.3)
    h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
    h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
    time.sleep(0.5)


def start_client(host, server_ip, mbps, port, tag, duration=600):
    host.cmd(
        f"iperf3 -c {server_ip} -p {port} -b {mbps}M "
        f"-t {duration} --forceflush -i 1 "
        f"2>&1 | tee /tmp/iperf_{tag}.log &"
    )


def start_ping(host, target_ip, tag, interval=1):
    host.cmd("pkill -f '^ping ' 2>/dev/null; true")
    time.sleep(0.2)
    host.cmd(
        f"ping -i {interval} {target_ip} "
        f"2>&1 | tee /tmp/ping_{tag}.log &"
    )
    time.sleep(0.3)


def stop_all(h1, h3, h2):
    h1.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
    h3.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
    h2.cmd("pkill -f iperf3      2>/dev/null; true")
    time.sleep(1)


def cleanup_demo_hosts(net):
    for name in DEMO_HOSTS:
        host = net.get(name)
        host.cmd("pkill -f iperf3    2>/dev/null; true")
        host.cmd("pkill -f '^ping ' 2>/dev/null; true")
        host.cmd("pkill -f mb1_telemetry.py 2>/dev/null; true")
        host.cmd("pkill -f mb2_security.py 2>/dev/null; true")
