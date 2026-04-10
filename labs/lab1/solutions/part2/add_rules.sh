#!/usr/bin/env bash
set -euo pipefail

OFCTL="sudo ovs-ofctl -O OpenFlow13"

$OFCTL del-flows s1

# h1 <-> h2
$OFCTL add-flow s1 "idle_timeout=0,ip,in_port=1,nw_src=10.0.0.1,nw_dst=10.0.0.2,actions=output:2"
$OFCTL add-flow s1 "idle_timeout=0,ip,in_port=2,nw_src=10.0.0.2,nw_dst=10.0.0.1,actions=output:1"

# h1 <-> h3
$OFCTL add-flow s1 "idle_timeout=0,ip,in_port=1,nw_src=10.0.0.1,nw_dst=10.0.0.3,actions=output:3"
$OFCTL add-flow s1 "idle_timeout=0,ip,in_port=3,nw_src=10.0.0.3,nw_dst=10.0.0.1,actions=output:1"

# h2 <-> h3: intentionally no rules.
# OVS drops any packet that does not match a rule, so h2 and h3 are isolated
# without needing an explicit drop action.

echo "Part 2 reference rules installed."
