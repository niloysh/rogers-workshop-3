#!/usr/bin/env bash

set -euo pipefail

pid="$(pgrep -f 'mininet:mb1' | head -1 || true)"

if [[ -z "${pid}" ]]; then
  echo "error: could not find Mininet host namespace for mb1" >&2
  echo "start lab3_topology.py first, then rerun this script" >&2
  exit 1
fi

echo "Starting mb1_firewall.py inside mb1 (pid ${pid})..."
exec sudo mnexec -a "${pid}" python3 mb1_firewall.py
