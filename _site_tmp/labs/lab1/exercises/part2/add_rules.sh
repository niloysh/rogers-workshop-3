#!/usr/bin/env bash
set -euo pipefail

# add_rules.sh — Part 2
# ---------------------
# Extend the rules so h1 can reach both h2 and h3,
# while h2 and h3 cannot reach each other.
#
# The h1 <-> h2 rules from Part 1 are pre-filled as a reference.
# Add the two missing rules for h1 <-> h3.
#
# Run from your second terminal:
#   sudo bash exercises/part2/add_rules.sh

OFCTL="sudo ovs-ofctl -O OpenFlow13"

$OFCTL del-flows s1

# h1 <-> h2 — pre-filled from Part 1 (use these as a reference for the TODOs below)
$OFCTL add-flow s1 "idle_timeout=0,ip,in_port=1,nw_src=10.0.0.1,nw_dst=10.0.0.2,actions=output:2"
$OFCTL add-flow s1 "idle_timeout=0,ip,in_port=2,nw_src=10.0.0.2,nw_dst=10.0.0.1,actions=output:1"

# TODO: add a rule so h1 can send packets to h3
# Hint: same pattern as above — adjust nw_dst and the output port number

# TODO: add a rule so h3 can send packets to h1

# Question: why can't h2 reach h3 even though they are on the same switch?
# Add your explanation as a comment here:
#

echo "Rules installed. Verify with: sudo python3 exercises/part2/verify.py"
