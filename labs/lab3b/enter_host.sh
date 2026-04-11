#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  cat <<'EOF' >&2
Usage:
  ./enter_host.sh <host>

Examples:
  ./enter_host.sh h2
  ./enter_host.sh mb1
  ./enter_host.sh mb2
EOF
  exit 1
fi

host="$1"
pid="$(pgrep -f "mininet:${host}" | head -1 || true)"

if [[ -z "${pid}" ]]; then
  echo "error: could not find Mininet host namespace for ${host}" >&2
  echo "start topology.py first, then rerun this command" >&2
  exit 1
fi

echo "Opening a shell inside ${host} (pid ${pid})..."
exec sudo mnexec -a "${pid}" env PS1="(${host}) \\u@\\h:\\w# " bash --noprofile --norc -i
