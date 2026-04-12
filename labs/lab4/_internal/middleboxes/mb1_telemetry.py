#!/usr/bin/env python3
"""
Telemetry monitor for mb1.

Counts SRv6 traffic delivered to mb1 and reports the observed throughput.
"""

import argparse
import signal
import socket
import sys
import time


ETH_P_ALL = 0x0003
ETH_P_IPV6 = b"\x86\xdd"
IPPROTO_ROUTING = 43
SRH_TYPE = 4


def is_srv6_packet(pkt, dst_mac):
    if len(pkt) < 14 + 40:
        return False
    if pkt[0:6] != dst_mac or pkt[12:14] != ETH_P_IPV6:
        return False
    if (pkt[14] >> 4) != 6:
        return False
    if pkt[20] != IPPROTO_ROUTING:
        return False
    return pkt[14 + 40 + 2] == SRH_TYPE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iface", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--dst-mac", required=True)
    args = parser.parse_args()

    dst_mac = bytes.fromhex(args.dst_mac.replace(":", ""))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
    sock.bind((args.iface, 0))
    sock.settimeout(1.0)

    open(args.log, "w").close()

    while True:
        total = 0
        deadline = time.time() + 1.0
        while time.time() < deadline:
            try:
                pkt = sock.recv(65535)
            except socket.timeout:
                break
            if is_srv6_packet(pkt, dst_mac):
                total += len(pkt)

        mbps = (total * 8) / 1_000_000
        ts = time.strftime("%H:%M:%S")
        label = "  <- telemetry sees slice traffic" if mbps > 0.01 else ""
        line = f"[mb1 telemetry] [{ts}]  {mbps:5.2f} Mbits/sec{label}\n"
        with open(args.log, "a") as logf:
            logf.write(line)
        sys.stdout.write(line)
        sys.stdout.flush()


if __name__ == "__main__":
    main()
