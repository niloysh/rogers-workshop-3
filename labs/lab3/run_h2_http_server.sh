#!/usr/bin/env bash

set -euo pipefail

pid="$(pgrep -f 'mininet:h2' | head -1 || true)"

if [[ -z "${pid}" ]]; then
  echo "error: could not find Mininet host namespace for h2" >&2
  echo "start lab3_topology.py first, then rerun this script" >&2
  exit 1
fi

echo "Starting Python HTTP server inside h2 (pid ${pid})..."
exec sudo mnexec -a "${pid}" python3 -m http.server 80 --bind 0.0.0.0
