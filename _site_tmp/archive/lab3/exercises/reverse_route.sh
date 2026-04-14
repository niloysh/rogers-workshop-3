#!/usr/bin/env bash
# Lab 3 — Independent Challenge
# ─────────────────────────────
# Install a reverse SRv6 route on h2 so that reply traffic is steered
# through the service chain: h2 → mb2 → mb1 → h1
#
# Fill in the two blanks below, then run:
#   sudo bash exercises/reverse_route.sh
#
# Reference:
#   Forward chain (already installed): h1 → mb1 → mb2 → h2
#     ip route add 10.0.0.2 encap seg6 mode encap segs fc00::b1,fc00::b2,fc00::2 dev h1-eth0
#
# SID table:
#   h1   fc00::1
#   h2   fc00::2
#   mb1  fc00::b1
#   mb2  fc00::b2

set -e

H2_PID=$(pgrep -f 'mininet:h2' | head -1)
if [ -z "$H2_PID" ]; then
    echo "[error] Mininet is not running or h2 is not found."
    echo "        Start the topology first: sudo python3 topology.py"
    exit 1
fi

echo "[lab3] Installing reverse SRv6 route on h2..."

# TODO: fill in the destination IP (h1's IPv4 address)
DESTINATION="_______"

# TODO: fill in the segs list for h2 → mb2 → mb1 → h1
#       (comma-separated SIDs, no spaces)
SEGS="_______"

sudo mnexec -a "$H2_PID" \
    ip route replace "$DESTINATION" \
    encap seg6 mode encap \
    segs "$SEGS" \
    dev h2-eth0

echo "[lab3] Route installed. Current routes on h2:"
sudo mnexec -a "$H2_PID" ip route show
