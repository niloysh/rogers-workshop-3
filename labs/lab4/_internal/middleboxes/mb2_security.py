#!/usr/bin/env python3
"""
Security inspector for mb2.

Inspects SRv6-encapsulated traffic delivered to mb2 and reports the inner
IPv4/TCP flow metadata. Traffic to the expected service port is marked [OK];
unexpected service ports are marked [ALERT].
"""

import argparse
import signal
import socket
import sys
import time


ETH_P_ALL = 0x0003
ETH_P_IPV6 = b"\x86\xdd"
IPPROTO_ROUTING = 43
IPPROTO_IPV4 = 4
IPPROTO_TCP = 6
SRH_TYPE = 4
EXPECTED_DPORTS = {5201}


def ipv4_to_str(raw):
    return ".".join(str(octet) for octet in raw)


def parse_inner_flow(pkt, dst_mac):
    if len(pkt) < 14 + 40:
        return None
    if pkt[0:6] != dst_mac or pkt[12:14] != ETH_P_IPV6:
        return None
    if (pkt[14] >> 4) != 6 or pkt[20] != IPPROTO_ROUTING:
        return None

    srh_offset = 14 + 40
    if len(pkt) < srh_offset + 8:
        return None
    if pkt[srh_offset + 2] != SRH_TYPE:
        return None

    inner_proto = pkt[srh_offset]
    srh_len = (pkt[srh_offset + 1] + 1) * 8
    inner_offset = srh_offset + srh_len

    if inner_proto != IPPROTO_IPV4 or len(pkt) < inner_offset + 20:
        return None
    if (pkt[inner_offset] >> 4) != 4:
        return None

    ip_header_len = (pkt[inner_offset] & 0x0F) * 4
    if len(pkt) < inner_offset + ip_header_len:
        return None
    if pkt[inner_offset + 9] != IPPROTO_TCP:
        return None

    tcp_offset = inner_offset + ip_header_len
    if len(pkt) < tcp_offset + 4:
        return None

    src_ip = ipv4_to_str(pkt[inner_offset + 12:inner_offset + 16])
    dst_ip = ipv4_to_str(pkt[inner_offset + 16:inner_offset + 20])
    src_port = int.from_bytes(pkt[tcp_offset:tcp_offset + 2], "big")
    dst_port = int.from_bytes(pkt[tcp_offset + 2:tcp_offset + 4], "big")

    return src_ip, dst_ip, src_port, dst_port


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
        flows = {}
        deadline = time.time() + 1.0
        while time.time() < deadline:
            try:
                pkt = sock.recv(65535)
            except socket.timeout:
                break
            flow = parse_inner_flow(pkt, dst_mac)
            if flow is not None:
                flows[flow] = flows.get(flow, 0) + 1

        ts = time.strftime("%H:%M:%S")
        if not flows:
            line = f"[mb2 security] [{ts}]  idle\n"
            with open(args.log, "a") as logf:
                logf.write(line)
            sys.stdout.write(line)
            sys.stdout.flush()
            continue

        lines = []
        for (src_ip, dst_ip, src_port, dst_port), count in sorted(flows.items()):
            status = "[OK]" if dst_port in EXPECTED_DPORTS else "[ALERT]"
            label = "expected service" if status == "[OK]" else "unexpected service port"
            lines.append(
                f"[mb2 security] [{ts}] {status} {src_ip}:{src_port} -> "
                f"{dst_ip}:{dst_port}  pkts={count}  {label}\n"
            )

        with open(args.log, "a") as logf:
            logf.writelines(lines)
        for line in lines:
            sys.stdout.write(line)
        sys.stdout.flush()


if __name__ == "__main__":
    main()
