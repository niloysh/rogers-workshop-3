#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REMOTE_DIR="~/workshop-bootstrap"
REMOTE_DIR="${REMOTE_DIR:-${DEFAULT_REMOTE_DIR}}"

usage() {
  cat <<EOF
Usage:
  scripts/push_bootstrap.sh <remote> [<remote> ...]

Description:
  Pushes the standalone workshop bootstrap scripts to one or more SSH remotes:
    - setup.sh
    - fetch_labs.sh

Environment variables:
  REMOTE_DIR   Destination directory on the remote host.
               Default: ${DEFAULT_REMOTE_DIR}

Examples:
  scripts/push_bootstrap.sh ws3
  scripts/push_bootstrap.sh ws3 ubuntu@10.0.0.20
  REMOTE_DIR=~/bin scripts/push_bootstrap.sh ws3
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "$#" -lt 1 ]]; then
  usage >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "error: rsync is required" >&2
  exit 1
fi

if ! command -v ssh >/dev/null 2>&1; then
  echo "error: ssh is required" >&2
  exit 1
fi

FILES=(
  "${SCRIPT_DIR}/setup.sh"
  "${SCRIPT_DIR}/fetch_labs.sh"
)

for file in "${FILES[@]}"; do
  if [[ ! -f "${file}" ]]; then
    echo "error: required file not found: ${file}" >&2
    exit 1
  fi
done

for remote in "$@"; do
  echo "==> Preparing ${remote}:${REMOTE_DIR}"
  ssh "${remote}" "mkdir -p ${REMOTE_DIR}"

  echo "==> Copying bootstrap scripts to ${remote}"
  rsync -av "${FILES[@]}" "${remote}:${REMOTE_DIR}/"

  echo "==> Marking scripts executable on ${remote}"
  ssh "${remote}" "chmod +x ${REMOTE_DIR}/setup.sh ${REMOTE_DIR}/fetch_labs.sh"

  echo "==> Done: ${remote}:${REMOTE_DIR}"
  echo "    Run on remote:"
  echo "      ${REMOTE_DIR}/setup.sh"
  echo "      ${REMOTE_DIR}/fetch_labs.sh"
  echo
done
