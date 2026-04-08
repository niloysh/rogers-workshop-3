#!/usr/bin/env bash

set -euo pipefail

REPO_OWNER="${REPO_OWNER:-niloysh}"
REPO_NAME="${REPO_NAME:-rogers-workshop-3}"
REPO_REF="${REPO_REF:-main}"
DEST_DIR="${DEST_DIR:-$HOME/labs}"
ARCHIVE_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/archive/refs/heads/${REPO_REF}.tar.gz"
TMP_DIR="$(mktemp -d)"
ARCHIVE_PATH="${TMP_DIR}/repo.tar.gz"
EXTRACT_DIR="${TMP_DIR}/extract"
REPO_ROOT_DIR="${REPO_NAME}-${REPO_REF}"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

usage() {
  cat <<EOF
Usage:
  scripts/fetch_labs.sh

Environment variables:
  REPO_OWNER  GitHub owner/org. Default: ${REPO_OWNER}
  REPO_NAME   GitHub repository. Default: ${REPO_NAME}
  REPO_REF    Branch name to fetch. Default: ${REPO_REF}
  DEST_DIR    Destination directory. Default: ${DEST_DIR}

What this does:
  - downloads the GitHub source tarball for the selected branch
  - extracts only the labs/ directory
  - writes it to DEST_DIR

Examples:
  scripts/fetch_labs.sh
  DEST_DIR=~/workshop-materials scripts/fetch_labs.sh
  REPO_REF=main scripts/fetch_labs.sh
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "error: curl is required" >&2
  exit 1
fi

if ! command -v tar >/dev/null 2>&1; then
  echo "error: tar is required" >&2
  exit 1
fi

echo "==> Fetching labs from GitHub"
echo "    repo: ${REPO_OWNER}/${REPO_NAME}"
echo "    ref:  ${REPO_REF}"
echo "    dest: ${DEST_DIR}"

mkdir -p "${EXTRACT_DIR}"

echo "==> Downloading archive"
curl -fL "${ARCHIVE_URL}" -o "${ARCHIVE_PATH}"

echo "==> Extracting labs/"
tar -xzf "${ARCHIVE_PATH}" -C "${EXTRACT_DIR}"

if [[ ! -d "${EXTRACT_DIR}/${REPO_ROOT_DIR}/labs" ]]; then
  echo "error: labs directory not found in downloaded archive" >&2
  exit 1
fi

DEST_DIR="$(eval echo "${DEST_DIR}")"

rm -rf "${DEST_DIR}"
mkdir -p "${DEST_DIR}"
cp -R "${EXTRACT_DIR}/${REPO_ROOT_DIR}/labs/." "${DEST_DIR}/"

echo
echo "Labs written to ${DEST_DIR}"
