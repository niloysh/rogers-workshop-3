#!/usr/bin/env bash
set -euo pipefail

# add_rules.sh — Part 1
# ---------------------
# Add two flow rules so that h1 and h2 can reach each other.
#
# Before filling this in, check which port on s1 connects to each host:
#   sudo ovs-ofctl -O OpenFlow13 show s1
#
# Then run this script from your second terminal:
#   sudo bash exercises/part1/add_rules.sh

OFCTL="sudo ovs-ofctl -O OpenFlow13"

$OFCTL del-flows s1

# TODO: add a rule so h1 can send packets to h2
# Match:  ip,in_port=<h1 port>,nw_src=10.0.0.1,nw_dst=10.0.0.2
# Action: output to h2's port

# TODO: add a rule so h2 can send packets to h1
# Same pattern in the opposite direction

echo "Rules installed. Verify with: sudo python3 exercises/part1/verify.py"
