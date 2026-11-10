#!/usr/bin/env bash
# Remote bootstrap for the 蜂群 DCU box.
#
# Creates the sandbox data root, clones (or pulls) this repo, and prints the
# exact commands to run the transformers serve + a smoke experiment. It is
# intentionally idempotent and side-effect-light: it does NOT download model
# weights or start the server. See docs/REMOTE_SETUP.md for the full manual.
#
# Target layout (matches README "工作区" section):
#   /root/private_data/agent_sandbox/
#     ├─ models/   <- Qwen2.5-14B weights land here (downloaded manually)
#     ├─ runs/     <- experiment run outputs
#     └─ code/     <- this git repo
#
# Usage (on 蜂群, after SSH-ing in):
#   bash remote_bootstrap.sh
#   # or override the repo URL / branch:
#   REPO_URL=https://github.com/Si-Nan-Si-Mu/multi-agent-sandbox-collusion.git \
#   REPO_BRANCH=main bash remote_bootstrap.sh

set -euo pipefail

SANDBOX_ROOT="${SANDBOX_ROOT:-/root/private_data/agent_sandbox}"
MODELS_DIR="${MODELS_DIR:-${SANDBOX_ROOT}/models}"
RUNS_DIR="${RUNS_DIR:-${SANDBOX_ROOT}/runs}"
CODE_DIR="${CODE_DIR:-${SANDBOX_ROOT}/code}"
REPO_URL="${REPO_URL:-https://github.com/Si-Nan-Si-Mu/multi-agent-sandbox-collusion.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"

log() { printf '[bootstrap] %s\n' "$*"; }

log "creating sandbox dirs under ${SANDBOX_ROOT}"
mkdir -p "${MODELS_DIR}" "${RUNS_DIR}"

if [[ -d "${CODE_DIR}/.git" ]]; then
  log "repo exists at ${CODE_DIR}; fetching + resetting to origin/${REPO_BRANCH}"
  git -C "${CODE_DIR}" fetch --prune origin
  git -C "${CODE_DIR}" checkout "${REPO_BRANCH}"
  git -C "${CODE_DIR}" reset --hard "origin/${REPO_BRANCH}"
else
  log "cloning ${REPO_URL} (branch ${REPO_BRANCH}) -> ${CODE_DIR}"
  mkdir -p "${CODE_DIR}"
  git clone --branch "${REPO_BRANCH}" "${REPO_URL}" "${CODE_DIR}"
fi

log "sandbox layout:"
log "  models -> ${MODELS_DIR}"
log "  runs   -> ${RUNS_DIR}"
log "  code   -> ${CODE_DIR}  @ $(git -C "${CODE_DIR}" rev-parse --short HEAD)"

log "next steps (manual, see docs/REMOTE_SETUP.md):"
log "  1) download Qwen2.5-14B weights into ${MODELS_DIR}"
log "  2) hy-smi  # check DCU memory"
log "  3) cd ${CODE_DIR}"
log "     MODEL_PATH=${MODELS_DIR}/Qwen2.5-14B MAX_NUM_SEQS=1 \\"
log "       python scripts/serve_llm_transformers.py"
log "  4) curl -s http://127.0.0.1:8001/v1/chat/completions -H 'Content-Type: application/json' \\"
log "       -d '{\"model\":\"Qwen2.5-14B\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":16}'"
log "  5) run the orchestrator smoke (N=2, max_steps=3) and record the run dir."

log "bootstrap done."
