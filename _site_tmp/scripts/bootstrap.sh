#!/usr/bin/env bash

set -euo pipefail

# GitHub repository details
REPO_OWNER="${REPO_OWNER:-niloysh}"
REPO_NAME="${REPO_NAME:-rogers-workshop-3}"
REPO_REF="${REPO_REF:-main}"
GITHUB_RAW_URL="https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${REPO_REF}"

# Flags
SKIP_SETUP=0
SKIP_FETCH=0

# Temporary directory for downloaded scripts
TMP_DIR="$(mktemp -d)"
SETUP_SCRIPT="${TMP_DIR}/setup.sh"
FETCH_LABS_SCRIPT="${TMP_DIR}/fetch_labs.sh"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

usage() {
  cat <<EOF
Usage:
  bootstrap.sh [OPTIONS]

Options:
  --skip-setup       Skip the setup step (Docker, ONOS, tools)
  --skip-fetch       Skip fetching labs from GitHub
  --help             Show this help message

Environment variables:
  REPO_OWNER         GitHub owner/org. Default: niloysh
  REPO_NAME          GitHub repository. Default: rogers-workshop-3
  REPO_REF           Branch name to fetch. Default: main
  ONOS_VERSION       ONOS version to install. Default: 2.7.0
  INSTALL_ONOS       Whether to install ONOS. Default: 1
  WORKSHOP_USER      User to configure for workshop. Default: current user or SUDO_USER
  DEST_DIR           Destination directory for labs. Default: \$HOME/labs

Examples:
  # Full initialization (download + setup + fetch labs)
  bash bootstrap.sh

  # Skip setup, only fetch labs
  bash bootstrap.sh --skip-setup

  # Setup only, don't fetch labs
  bash bootstrap.sh --skip-fetch

  # Fetch labs to custom location
  DEST_DIR=~/my-labs bash bootstrap.sh --skip-setup
EOF
}

die() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

resolve_dest_dir() {
  local raw_dest="${DEST_DIR:-$HOME/labs}"
  eval echo "${raw_dest}"
}

ensure_safe_dest_dir() {
  local dest_dir="$1"

  [[ -n "${dest_dir}" ]] || die "destination directory resolved to an empty path"
  [[ "${dest_dir}" != "/" ]] || die "refusing to use '/' as destination directory"
  [[ "${dest_dir}" != "${HOME}" ]] || die "refusing to use '$HOME' as destination directory"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-setup)
      SKIP_SETUP=1
      shift
      ;;
    --skip-fetch)
      SKIP_FETCH=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option '$1'" >&2
      usage
      exit 1
      ;;
  esac
done

# Validate at least one action is being taken
if [[ "${SKIP_SETUP}" -eq 1 && "${SKIP_FETCH}" -eq 1 ]]; then
  die "cannot skip both setup and fetch"
fi

echo "==> Rogers Workshop 3 Bootstrap"
echo

# Ensure minimal dependencies are available
if [[ "${SKIP_SETUP}" -eq 0 || "${SKIP_FETCH}" -eq 0 ]]; then
  echo "==> Ensuring minimal dependencies"
  
  if ! command -v curl >/dev/null 2>&1; then
    echo "Installing curl..."
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get update -o Acquire::Retries=3
      sudo apt-get install -y curl
    elif command -v yum >/dev/null 2>&1; then
      sudo yum install -y curl
    else
      die "unable to install curl; please install manually"
    fi
  fi

  if ! command -v tar >/dev/null 2>&1; then
    echo "Installing tar..."
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get install -y tar
    elif command -v yum >/dev/null 2>&1; then
      sudo yum install -y tar
    else
      die "unable to install tar; please install manually"
    fi
  fi
  
  echo
fi

# Download and run setup if not skipped
if [[ "${SKIP_SETUP}" -eq 0 ]]; then
  echo "==> Downloading setup script"
  if ! curl -fsSL "${GITHUB_RAW_URL}/scripts/setup.sh" -o "${SETUP_SCRIPT}"; then
    die "failed to download setup script from ${GITHUB_RAW_URL}/scripts/setup.sh"
  fi
  
  echo "==> Running setup"
  bash "${SETUP_SCRIPT}"
  echo
else
  echo "(skipped setup as requested)"
  echo
fi

# Download and run fetch_labs if not skipped
if [[ "${SKIP_FETCH}" -eq 0 ]]; then
  DEST_DIR="$(resolve_dest_dir)"
  ensure_safe_dest_dir "${DEST_DIR}"

  if [[ -e "${DEST_DIR}" ]]; then
    echo "==> Removing existing labs directory at ${DEST_DIR}"
    rm -rf "${DEST_DIR}"
  fi

  echo "==> Downloading fetch_labs script"
  if ! curl -fsSL "${GITHUB_RAW_URL}/scripts/fetch_labs.sh" -o "${FETCH_LABS_SCRIPT}"; then
    die "failed to download fetch_labs script from ${GITHUB_RAW_URL}/scripts/fetch_labs.sh"
  fi
  
  echo "==> Running fetch_labs"
  DEST_DIR="${DEST_DIR}" bash "${FETCH_LABS_SCRIPT}"
  echo
else
  echo "(skipped fetch_labs as requested)"
  echo
fi

echo "==> Initialization complete"
