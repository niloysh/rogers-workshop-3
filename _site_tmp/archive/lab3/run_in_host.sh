#!/usr/bin/env bash

set -euo pipefail

echo "run_in_host.sh has been renamed for clarity."
echo "Use: ./enter_host.sh <host>"
exec "$(dirname "$0")/enter_host.sh" "$@"
