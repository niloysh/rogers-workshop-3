#!/usr/bin/env bash
set -euo pipefail

# install_rules.sh
# ----------------
# Participant starter for the Lab 1 challenge flow rules.
#
# Fill in the TODO sections, then run:
#
#   sudo bash install_rules.sh
#
# Expected behavior after your rules are in place:
#   - h1 <-> h2 works
#   - h1 <-> h3 works
#   - h2 <-> h3 does not work

OFCTL="sudo ovs-ofctl -O OpenFlow13"

# Clear any old rules before installing new ones.
$OFCTL del-flows s1
$OFCTL del-flows s2
$OFCTL del-flows s3
$OFCTL del-flows s4

# TODO: add rules for h1 <-> h2 via s1 -> s2

# TODO: add rules for h1 <-> h3 via s1 -> s3 -> s4

echo "Rule installation complete. Verify with: sudo python3 verify_challenge.py"
