# Remote setup on 蜂群 (DCU)

This document describes how to run the **first remote smoke** of the
multi-agent sandbox experiment on the 蜂群 DCU box. It is intentionally
manual: the bootstrap script creates directories and clones the repo, but
weight download, `hy-smi` checks, server start, and the orchestrator smoke are
run by hand so we can watch each step.

> Remote smoke is **manual**. The CI/local test path uses `MockLLM` and does
> not touch the DCU box. See the README "Smoke" section for the policy.

## 0. Prerequisites

- SSH access to the 蜂群 DCU box (Notebook / SSH entry, separate from the
  EmbedX experiment machine).
- DCU-enabled torch + `transformers` installed in the remote env.
- `git`, `curl`, `hy-smi` available on PATH.
- Enough DCU HBM for the chosen model (see §5 OOM handling).

## 1. Bootstrap the sandbox

```bash
# on 蜂群, after SSH-ing in
cd ~
bash remote_bootstrap.sh
# override defaults if needed:
# SANDBOX_ROOT=/root/private_data/agent_sandbox \
# REPO_URL=https://github.com/Si-Nan-Si-Mu/multi-agent-sandbox-collusion.git \
# REPO_BRANCH=main bash remote_bootstrap.sh
```

This creates:

```
/root/private_data/agent_sandbox/
  ├─ models/   # weights land here
  ├─ runs/     # experiment outputs
  └─ code/     # this repo (cloned or pulled to origin/<branch>)
```

## 2. Download Qwen2.5-14B weights

```bash
cd /root/private_data/agent_sandbox/models
# option A: modelscope
pip install modelscope
python -c "from modelscope import snapshot_download; \
  snapshot_download('Qwen/Qwen2.5-14B-Instruct', local_dir='./Qwen2.5-14B')"
# option B: huggingface-cli
pip install -U huggingface_hub
huggingface-cli download Qwen/Qwen2.5-14B-Instruct \
  --local-dir ./Qwen2.5-14B
```

Verify the snapshot:

```bash
ls -lh /root/private_data/agent_sandbox/models/Qwen2.5-14B
# expect: config.json, model-*.safetensors, tokenizer files, ...
```

## 3. Check DCU memory with `hy-smi`

```bash
hy-smi
```

Look at the free HBM column. For Qwen2.5-14B fp16 you need roughly ~28-30 GB
free on a single DCU. If free memory is below that, either:

- switch to an INT4/AWQ checkpoint (M32Q profile), or
- set `MAX_NUM_SEQS=1` and accept strict serial generation, or
- move to a device with more HBM.

## 4. Start the transformers serve

```bash
cd /root/private_data/agent_sandbox/code
MODEL_PATH=/root/private_data/agent_sandbox/models/Qwen2.5-14B \
MAX_NUM_SEQS=1 \
DTYPE=float16 \
python scripts/serve_llm_transformers.py
```

Server binds `0.0.0.0:8001` and exposes:

- `GET  /v1/health` -> `{status, model, max_num_seqs, device, dtype}`
- `GET  /v1/models` -> OpenAI-style model list
- `POST /v1/chat/completions` -> OpenAI-style chat completion

`MAX_NUM_SEQS=1` uses a global `asyncio.Lock` (strict serial, OOM-safe). Set
`MAX_NUM_SEQS=2` to use a bounded semaphore for the M14-N16 matrix; only do
this after §3 confirms enough HBM.

## 5. Curl one completion

```bash
curl -s http://127.0.0.1:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen2.5-14B",
    "messages": [
      {"role": "user", "content": "Reply with the single word: pong"}
    ],
    "max_tokens": 16
  }' | python -m json.tool
```

Expected shape:

```json
{
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "pong"},
      "finish_reason": "stop"
    }
  ]
}
```

### OOM handling

If the server OOMs during load or during the first request:

1. Stop the server.
2. Re-run `hy-smi`; confirm free HBM.
3. Restart with `MAX_NUM_SEQS=1` (if it was higher).
4. If still OOMing, switch `DTYPE=bfloat16` or move to the INT4/AWQ checkpoint
   (M32Q profile, which forces `max_num_seqs=1` in `RunConfig`).

## 6. Run the orchestrator smoke

With the server up in another shell:

```bash
cd /root/private_data/agent_sandbox/code
python scripts/run_local_mock.py --n-agents 2 --max-steps 3 \
  --run-dir /root/private_data/agent_sandbox/runs/smoke-001
```

> NOTE: `run_local_mock.py` currently drives a `MockLLM`. To point the
> orchestrator at the real 14B server, set the env / config so that
> `RunConfig.llm_base_url = http://127.0.0.1:8001/v1` and an
> `OpenAICompatClient` is used in place of `MockLLM`. Record the actual run
> directory path in the README "Smoke" section.

## 7. Record the smoke result

In `README.md` "Smoke" section, append a one-liner, e.g.:

```
- 2026-11-10 蜂群 DCU, Qwen2.5-14B fp16, N=2 max_steps=3:
  run dir /root/private_data/agent_sandbox/runs/smoke-001, milestones=<path>
```

## 8. Tear down

```bash
# stop the server (Ctrl-C in its shell)
# optionally free the checkout:
rm -rf /root/private_data/agent_sandbox/code
# keep runs/ and models/ for reuse
```
