#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/assets/slides"
THEME_WORKSHOP="${REPO_ROOT}/assets/css/marp.css"
THEME_WORKSHOP_READABLE="${REPO_ROOT}/assets/css/marp-readable.css"

if ! command -v marp >/dev/null 2>&1; then
  echo "error: marp CLI is not installed or not on PATH" >&2
  echo "install it first, then rerun this script" >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"

render_one() {
  local source_file="$1"
  local output_name="$2"
  local output_file="${OUTPUT_DIR}/${output_name}.html"

  echo "Rendering ${source_file} -> ${output_file}"
  marp \
    "${REPO_ROOT}/${source_file}" \
    --html \
    --theme-set "${THEME_WORKSHOP}" \
    --theme-set "${THEME_WORKSHOP_READABLE}" \
    -o "${output_file}"
}

render_target() {
  case "$1" in
    lab1)
      render_one "labs/lab1/lab1.md" "lab1"
      ;;
    lab2)
      render_one "labs/lab2/lab2.md" "lab2"
      ;;
    *)
      echo "error: unknown target '$1'" >&2
      echo "usage: scripts/render_slides.sh [lab1] [lab2]" >&2
      exit 1
      ;;
  esac
}

if [ "$#" -eq 0 ]; then
  render_target lab1
  render_target lab2
else
  for target in "$@"; do
    render_target "${target}"
  done
fi

echo
echo "Slides written to ${OUTPUT_DIR}"
