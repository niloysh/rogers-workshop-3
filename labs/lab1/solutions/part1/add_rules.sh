#!/usr/bin/env bash
set -euo pipefail

OFCTL="sudo ovs-ofctl -O OpenFlow13"

$OFCTL del-flows s1

# h1 <-> h2
$OFCTL add-flow s1 "idle_timeout=0,ip,in_port=1,nw_src=10.0.0.1,nw_dst=10.0.0.2,actions=output:2"
$OFCTL add-flow s1 "idle_timeout=0,ip,in_port=2,nw_src=10.0.0.2,nw_dst=10.0.0.1,actions=output:1"

echo "Part 1 reference rules installed."
