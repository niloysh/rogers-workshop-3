#!/usr/bin/env bash
# Lab 3 — Reference solution
# ──────────────────────────
# Reverse SRv6 route on h2: h2 → mb2 → mb1 → h1
#
# Why mb2 before mb1?
#   The reverse chain mirrors the forward chain from h2's perspective.
#   Forward: h1 exits → mb1 → mb2 → h2 arrives.
#   Reverse: h2 exits → mb2 → mb1 → h1 arrives.
#   Reversing the waypoint order ensures traffic passes through the same
#   service functions in the opposite direction.

set -e

H2_PID=$(pgrep -f 'mininet:h2' | head -1)

echo "[solution] Installing reverse SRv6 route on h2..."

sudo mnexec -a "$H2_PID" \
    ip route replace 10.0.0.1 \
    encap seg6 mode encap \
    segs fc00::b2,fc00::b1,fc00::1 \
    dev h2-eth0

echo "[solution] Route installed. Current routes on h2:"
sudo mnexec -a "$H2_PID" ip route show
