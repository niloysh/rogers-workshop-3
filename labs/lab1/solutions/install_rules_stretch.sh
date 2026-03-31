#!/usr/bin/env bash
set -euo pipefail

# Stretch solution:
# - keep h1 <-> h2 on s1 -> s2
# - reroute h1 <-> h3 over s1 -> s2 -> s4

OFCTL="sudo ovs-ofctl -O OpenFlow13"

$OFCTL del-flows s1
$OFCTL del-flows s2
$OFCTL del-flows s3
$OFCTL del-flows s4

# h1 <-> h2 via s1 -> s2
$OFCTL add-flow s1 \
  "idle_timeout=0,ip,in_port=1,nw_src=10.0.0.1,nw_dst=10.0.0.2,actions=output:2"
$OFCTL add-flow s1 \
  "idle_timeout=0,ip,in_port=2,nw_src=10.0.0.2,nw_dst=10.0.0.1,actions=output:1"

$OFCTL add-flow s2 \
  "idle_timeout=0,ip,in_port=2,nw_src=10.0.0.1,nw_dst=10.0.0.2,actions=output:1"
$OFCTL add-flow s2 \
  "idle_timeout=0,ip,in_port=1,nw_src=10.0.0.2,nw_dst=10.0.0.1,actions=output:2"

# h1 <-> h3 via s1 -> s2 -> s4
$OFCTL add-flow s1 \
  "idle_timeout=0,ip,in_port=1,nw_src=10.0.0.1,nw_dst=10.0.0.3,actions=output:2"
$OFCTL add-flow s1 \
  "idle_timeout=0,ip,in_port=2,nw_src=10.0.0.3,nw_dst=10.0.0.1,actions=output:1"

$OFCTL add-flow s2 \
  "idle_timeout=0,ip,in_port=2,nw_src=10.0.0.1,nw_dst=10.0.0.3,actions=output:3"
$OFCTL add-flow s2 \
  "idle_timeout=0,ip,in_port=3,nw_src=10.0.0.3,nw_dst=10.0.0.1,actions=output:2"

$OFCTL add-flow s4 \
  "idle_timeout=0,ip,in_port=2,nw_src=10.0.0.1,nw_dst=10.0.0.3,actions=output:1"
$OFCTL add-flow s4 \
  "idle_timeout=0,ip,in_port=1,nw_src=10.0.0.3,nw_dst=10.0.0.1,actions=output:2"

echo "Stretch rules installed."
