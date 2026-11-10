#!/usr/bin/env bash
# Pack one experiment run and leave model weights out of the archive.
#
# Usage:
#   bash scripts/pack_run.sh <run_id>
#
# Reads ${RUNS_ROOT:-<repo>/runs}/<run_id> and writes
# ${PACK_DIR:-<repo>/packs}/<run_id>.tar.gz.
# Members are stored as <run_id>/... so the tarball unpacks as one run.
#
# Excluded anywhere under the run (same weight types as .gitignore):
#   *.bin *.safetensors *.gguf *.pt *.pth
#   directories named models or weights
#
# Env:
#   RUNS_ROOT   parent of <run_id> (default <repo>/runs)
#   PACK_DIR    output directory (default <repo>/packs)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNS_ROOT="${RUNS_ROOT:-${ROOT}/runs}"
PACK_DIR="${PACK_DIR:-${ROOT}/packs}"

die() { printf '[pack] ERROR: %s\n' "$*" >&2; exit 1; }

if [[ $# -ne 1 || -z "${1}" ]]; then
  die "usage: bash scripts/pack_run.sh <run_id>"
fi

run_id="$1"
if [[ ! "${run_id}" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
  die "run id must be a single directory name"
fi

src="${RUNS_ROOT}/${run_id}"
if [[ ! -d "${src}" ]]; then
  die "run directory not found: ${src}"
fi

mkdir -p "${PACK_DIR}"
out="${PACK_DIR}/${run_id}.tar.gz"
rm -f "${out}"

tar -czf "${out}" \
  --exclude='*.bin' \
  --exclude='*.safetensors' \
  --exclude='*.gguf' \
  --exclude='*.pt' \
  --exclude='*.pth' \
  --exclude='*/models' \
  --exclude='*/models/*' \
  --exclude='models' \
  --exclude='models/*' \
  --exclude='*/weights' \
  --exclude='*/weights/*' \
  --exclude='weights' \
  --exclude='weights/*' \
  -C "${RUNS_ROOT}" \
  "${run_id}"

printf '[pack] wrote %s\n' "${out}"
