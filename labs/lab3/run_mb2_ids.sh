#!/usr/bin/env bash

set -euo pipefail

pid="$(pgrep -f 'mininet:mb2' | head -1 || true)"

if [[ -z "${pid}" ]]; then
  echo "error: could not find Mininet host namespace for mb2" >&2
  echo "start topology.py first, then rerun this script" >&2
  exit 1
fi

echo "Starting mb2_ids.py inside mb2 (pid ${pid})..."
exec sudo mnexec -a "${pid}" python3 mb2_ids.py
