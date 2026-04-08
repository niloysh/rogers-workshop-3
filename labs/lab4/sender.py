#!/usr/bin/env python3
"""
sender.py
─────────
Simple paced UDP sender for the revised Lab 4 demos.

The sender embeds a sequence number and send timestamp in each packet so the
receiver can estimate throughput, latency, jitter, and loss.
"""

import argparse
import socket
import struct
import time


HEADER = struct.Struct("!Id")


def parse_args():
    parser = argparse.ArgumentParser(description="Paced UDP sender for Lab 4")
    parser.add_argument("--host", required=True, help="Destination IPv4 address")
    parser.add_argument("--port", type=int, default=5005, help="Destination UDP port")
    parser.add_argument("--rate", type=float, default=1.0, help="Target rate in Mbps")
    parser.add_argument("--pkt-size", type=int, default=1000, help="Packet size in bytes")
    parser.add_argument(
        "--duration",
        type=float,
        default=20.0,
        help="How long to send traffic, in seconds",
    )
    parser.add_argument(
        "--label",
        default="flow",
        help="Short label shown in sender status messages",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.pkt_size <= HEADER.size:
        raise SystemExit(f"--pkt-size must be > {HEADER.size} bytes")
    if args.rate <= 0:
        raise SystemExit("--rate must be > 0 Mbps")
    if args.duration <= 0:
        raise SystemExit("--duration must be > 0 seconds")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload_size = args.pkt_size - HEADER.size
    send_interval = (args.pkt_size * 8) / (args.rate * 1_000_000)

    print(
        f"[sender:{args.label}] sending to {args.host}:{args.port} "
        f"at {args.rate:.2f} Mbps for {args.duration:.1f}s "
        f"({args.pkt_size}B packets)"
    )

    seq = 0
    sent_bytes = 0
    started = time.time()
    next_send = started
    next_report = started + 1.0

    while True:
        now = time.time()
        if now - started >= args.duration:
            break

        packet = HEADER.pack(seq, now) + (b"x" * payload_size)
        sock.sendto(packet, (args.host, args.port))
        seq += 1
        sent_bytes += len(packet)

        if now >= next_report:
            elapsed = now - started
            avg_rate = (sent_bytes * 8) / (elapsed * 1_000_000)
            print(
                f"[sender:{args.label}] t={elapsed:>4.1f}s "
                f"packets={seq:>7} avg_rate={avg_rate:>5.2f} Mbps"
            )
            next_report += 1.0

        next_send += send_interval
        sleep_time = next_send - time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)

    elapsed = max(time.time() - started, 1e-9)
    avg_rate = (sent_bytes * 8) / (elapsed * 1_000_000)
    print(
        f"[sender:{args.label}] done: packets={seq}, bytes={sent_bytes}, "
        f"avg_rate={avg_rate:.2f} Mbps over {elapsed:.2f}s"
    )


if __name__ == "__main__":
    main()
