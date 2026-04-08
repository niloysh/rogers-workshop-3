#!/usr/bin/env python3
"""
receiver.py
───────────
Simple UDP receiver for the revised Lab 4 demos.

It expects packets produced by sender.py and prints one line of measurements
per reporting interval.
"""

import argparse
import socket
import struct
import time


HEADER = struct.Struct("!Id")


def parse_args():
    parser = argparse.ArgumentParser(description="UDP receiver for Lab 4")
    parser.add_argument("--port", type=int, default=5005, help="UDP port to listen on")
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between measurement reports",
    )
    parser.add_argument(
        "--label",
        default="flow",
        help="Short label shown in receiver output",
    )
    return parser.parse_args()


def average_jitter(latencies_ms):
    if len(latencies_ms) < 2:
        return 0.0
    deltas = [
        abs(latencies_ms[index] - latencies_ms[index - 1])
        for index in range(1, len(latencies_ms))
    ]
    return sum(deltas) / len(deltas)


def main():
    args = parse_args()
    if args.interval <= 0:
        raise SystemExit("--interval must be > 0 seconds")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))
    sock.settimeout(0.2)

    print(f"[receiver:{args.label}] listening on UDP port {args.port}")
    print(
        f"{'Throughput':>12}  {'Latency':>10}  {'Jitter':>10}  "
        f"{'Loss':>8}  {'Pkts':>8}"
    )

    last_print = time.time()
    bytes_recv = 0
    latencies_ms = []
    packets_recv = 0
    expected_next_seq = None
    lost_packets = 0

    while True:
        try:
            data, _addr = sock.recvfrom(65535)
            recv_time = time.time()
            if len(data) < HEADER.size:
                continue

            seq, send_time = HEADER.unpack(data[: HEADER.size])
            latency_ms = (recv_time - send_time) * 1000
            latencies_ms.append(latency_ms)
            bytes_recv += len(data)
            packets_recv += 1

            if expected_next_seq is None:
                expected_next_seq = seq + 1
            else:
                if seq > expected_next_seq:
                    lost_packets += seq - expected_next_seq
                expected_next_seq = seq + 1
        except socket.timeout:
            pass

        now = time.time()
        if now - last_print < args.interval:
            continue

        elapsed = now - last_print
        throughput_mbps = (bytes_recv * 8) / (elapsed * 1_000_000)
        avg_latency = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0
        jitter_ms = average_jitter(latencies_ms)
        total_packets = packets_recv + lost_packets
        loss_pct = (lost_packets / total_packets * 100) if total_packets else 0.0

        print(
            f"{throughput_mbps:>9.2f} Mbps  "
            f"{avg_latency:>8.2f} ms  "
            f"{jitter_ms:>8.2f} ms  "
            f"{loss_pct:>6.2f}%  "
            f"{packets_recv:>8}"
        )

        last_print = now
        bytes_recv = 0
        latencies_ms = []
        packets_recv = 0
        lost_packets = 0


if __name__ == "__main__":
    main()
