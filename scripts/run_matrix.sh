#!/usr/bin/env bash
# Experiment matrix runner: M14-N12/16 and M32Q-N4/8.
#
# Loops seeds 1 2 3 (override with SEEDS) and, for each config, writes
#   ${RUNS_ROOT}/<profile>_n<N>_seed<S>/
# where <profile> is the lowercased model_profile (m14 / m32q) and <N> is
# n_agents. seed and run_dir inside the JSON are placeholders; this script
# overwrites both per iteration.
#
# Before any run, queries hy-smi and refuses to start when parsed VRAM use
# is above HY_SMI_VRAM_MAX_PCT (default 10). If hy-smi is not on PATH, the
# check is skipped with a warning so the script still works on Windows and
# other non-DCU hosts.
#
# Does not download weights and does not start the model server. An
# OpenAI-compatible server (scripts/serve_llm_transformers.py) must already
# be listening at each config's llm_base_url. Only one weight set may be
# loaded; free the card before switching M14 <-> M32Q. M32Q has not been
# verified on DCU — see docs/M32Q_STATUS.md.
#
# Usage:
#   bash scripts/run_matrix.sh
#   SEEDS="1" bash scripts/run_matrix.sh configs/m14_n12.json
#   DRY_RUN=1 bash scripts/run_matrix.sh
#
# Env:
#   SEEDS                 space-separated seeds (default "1 2 3")
#   RUNS_ROOT             output root (default <repo>/runs)
#   DRY_RUN               1 = print planned run dirs, do not call the LLM
#   HY_SMI_VRAM_MAX_PCT   refuse when used VRAM percent is greater than this
#   PYTHON                python interpreter (default python)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

PYTHON="${PYTHON:-python}"
SEEDS="${SEEDS:-1 2 3}"
RUNS_ROOT="${RUNS_ROOT:-${ROOT}/runs}"
DRY_RUN="${DRY_RUN:-0}"
HY_SMI_VRAM_MAX_PCT="${HY_SMI_VRAM_MAX_PCT:-10}"

log() { printf '[matrix] %s\n' "$*"; }
warn() { printf '[matrix] WARNING: %s\n' "$*" >&2; }
die() { printf '[matrix] ERROR: %s\n' "$*" >&2; exit 1; }

# Read hy-smi text on stdin. Print the max VRAM percent, or NOPARSE.
parse_vram_pct() {
  "${PYTHON}" -c '
import re
import sys

text = sys.stdin.read()
pcts = []

def grab(pat):
    return [float(x) for x in re.findall(pat, text, flags=re.I)]

used = grab(r"VRAM Total Used Memory \(MiB\):\s*([0-9]+(?:\.[0-9]+)?)")
total = grab(r"VRAM Total(?!\s+Used) Memory \(MiB\):\s*([0-9]+(?:\.[0-9]+)?)")
for u, t in zip(used, total):
    if t > 0:
        pcts.append(100.0 * u / t)

for u, t in re.findall(
    r"([0-9]+(?:\.[0-9]+)?)\s*MiB\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*MiB",
    text,
    flags=re.I,
):
    t = float(t)
    if t > 0:
        pcts.append(100.0 * float(u) / t)

if re.search(r"VRAM\s*%", text, flags=re.I):
    for line in text.splitlines():
        if re.search(r"VRAM\s*%", line, flags=re.I):
            continue
        if not re.match(r"\s*\d+\b", line):
            continue
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
        if m:
            pcts.append(float(m.group(1)))

if not pcts:
    print("NOPARSE")
else:
    print("%.4f" % max(pcts))
'
}

check_vram() {
  if ! command -v hy-smi >/dev/null 2>&1; then
    warn "hy-smi not found on PATH; skipping VRAM check."
    return 0
  fi
  local out pct
  if ! out="$(hy-smi 2>&1)"; then
    warn "hy-smi exited non-zero; skipping VRAM check."
    printf '%s\n' "${out}" >&2
    return 0
  fi
  pct="$(printf '%s\n' "${out}" | parse_vram_pct)"
  pct="${pct//$'\r'/}"
  if [[ "${pct}" == "NOPARSE" || -z "${pct}" ]]; then
    warn "hy-smi output had no parseable VRAM field; skipping VRAM check."
    return 0
  fi
  log "hy-smi VRAM use ${pct}% (limit ${HY_SMI_VRAM_MAX_PCT}%)"
  if ! "${PYTHON}" -c 'import sys; used=float(sys.argv[1]); limit=float(sys.argv[2]); sys.exit(0 if used <= limit else 1)' \
      "${pct}" "${HY_SMI_VRAM_MAX_PCT}"; then
    die "refusing to start: hy-smi VRAM use ${pct}% exceeds ${HY_SMI_VRAM_MAX_PCT}%. Free the DCU or raise HY_SMI_VRAM_MAX_PCT."
  fi
}

# Print "<profile>\n<n_agents>" after validating the JSON as RunConfig.
read_meta() {
  "${PYTHON}" -c '
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")
from agent_sandbox.config import RunConfig

raw = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
cfg = RunConfig.model_validate(raw)
profile = cfg.model_profile.lower()
if not profile.replace("_", "").isalnum():
    raise SystemExit("unsafe model_profile: %s" % cfg.model_profile)
print(profile)
print(cfg.n_agents)
' "$1"
}

run_one() {
  local cfg="$1" seed="$2" run_dir="$3"
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "DRY_RUN seed=${seed} -> ${run_dir}"
    return 0
  fi
  mkdir -p "${run_dir}"
  MATRIX_CONFIG="${cfg}" MATRIX_SEED="${seed}" MATRIX_RUN_DIR="${run_dir}" \
    "${PYTHON}" - <<'PY'
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "src")
from agent_sandbox.config import RunConfig
from agent_sandbox.llm_client import OpenAICompatClient
from agent_sandbox.orchestrator import run_experiment

raw = json.loads(Path(os.environ["MATRIX_CONFIG"]).read_text(encoding="utf-8"))
raw["seed"] = int(os.environ["MATRIX_SEED"])
raw["run_dir"] = os.environ["MATRIX_RUN_DIR"]
cfg = RunConfig.model_validate(raw)
llm = OpenAICompatClient(
    cfg.llm_base_url,
    cfg.model_name,
    max_tokens=cfg.max_tokens,
)
summary = run_experiment(cfg, llm)
out = Path(cfg.run_dir) / "summary.json"
out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
PY
}

main() {
  local configs=("$@")
  if [[ ${#configs[@]} -eq 0 ]]; then
    configs=(
      configs/m14_n12.json
      configs/m14_n16.json
      configs/m32q_n4.json
      configs/m32q_n8.json
    )
  fi

  check_vram

  local cfg seed meta profile n run_dir
  for cfg in "${configs[@]}"; do
    [[ -f "${cfg}" ]] || die "config not found: ${cfg}"
    meta="$(read_meta "${cfg}")"
    meta="${meta//$'\r'/}"
    profile="$(printf '%s\n' "${meta}" | sed -n '1p')"
    n="$(printf '%s\n' "${meta}" | sed -n '2p')"
    [[ -n "${profile}" && -n "${n}" ]] || die "failed to read ${cfg}"
    case "${profile}" in
      m32q)
        warn "M32Q is not verified on DCU yet; see docs/M32Q_STATUS.md"
        ;;
    esac
    for seed in ${SEEDS}; do
      run_dir="${RUNS_ROOT}/${profile}_n${n}_seed${seed}"
      log "config=${cfg} profile=${profile} n=${n} seed=${seed}"
      run_one "${cfg}" "${seed}" "${run_dir}"
    done
  done
  log "matrix run finished."
}

main "$@"
