"""OpenAI-compatible HTTP server backed by a HuggingFace causal LM.

This is the *minimal* serve path used for the first remote smoke on the
蜂群 DCU box. It deliberately avoids vLLM and instead loads a causal LM with
`transformers` on `cuda:0` (DCU torch) and generates with a global lock or
semaphore controlled by `MAX_NUM_SEQS`.

Endpoint contract (matches `agent_sandbox.llm_client.OpenAICompatClient` and
`RunConfig.llm_base_url = http://127.0.0.1:8001/v1`):

    POST /v1/chat/completions
    request:  {"model": "...", "messages": [...], "max_tokens": 768, ...}
    response: {"choices": [{"message": {"role": "assistant", "content": "..."}}]}

Environment variables:
    MODEL_PATH     - local path or HF repo id of the causal LM (required).
    MAX_NUM_SEQS   - concurrency cap; 1 -> a global asyncio.Lock, >1 -> semaphore
                     (default: 1, the OOM-safe choice).
    HOST / PORT    - bind address (default 0.0.0.0:8001).
    MODEL_NAME     - value echoed back in responses (default: basename of MODEL_PATH).
    DTYPE          - torch dtype string, e.g. "float16", "bfloat16", "float32"
                     (default: "float16").
    DEVICE         - device map string (default: "cuda:0").
    MAX_NEW_TOKENS_FALLBACK - default max_new_tokens when request omits it
                     (default: 768).

Usage:
    MODEL_PATH=/root/private_data/agent_sandbox/models/Qwen2.5-14B \\
    MAX_NUM_SEQS=1 python scripts/serve_llm_transformers.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

# NOTE: heavy imports (torch / transformers / fastapi / uvicorn) are deferred so
# that `python -m py_compile` and lightweight tooling can load this module on
# machines that do not yet have the DCU stack installed.

log = logging.getLogger("serve_llm_transformers")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - env misconfig
        raise SystemExit(f"{name} must be an integer, got {raw!r}") from exc


def _build_app() -> Any:
    """Construct and return the FastAPI app with the model loaded.

    Imports of torch/transformers/fastapi happen here so the module remains
    importable without the DCU stack present.
    """
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    model_path = os.environ.get("MODEL_PATH")
    if not model_path:
        raise SystemExit(
            "MODEL_PATH env var is required "
            "(e.g. /root/private_data/agent_sandbox/models/Qwen2.5-14B)"
        )
    max_num_seqs = max(1, _env_int("MAX_NUM_SEQS", 1))
    host = os.environ.get("HOST", "0.0.0.0")
    port = _env_int("PORT", 8001)
    model_name = os.environ.get("MODEL_NAME") or Path(model_path).name
    dtype_str = os.environ.get("DTYPE", "float16")
    device = os.environ.get("DEVICE", "cuda:0")
    max_new_tokens_fallback = _env_int("MAX_NEW_TOKENS_FALLBACK", 768)

    import torch  # type: ignore
    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

    dtype_map = {
        "float16": torch.float16,
        "fp16": torch.float16,
        "bfloat16": torch.bfloat16,
        "bf16": torch.bfloat16,
        "float32": torch.float32,
        "fp32": torch.float32,
    }
    if dtype_str not in dtype_map:
        raise SystemExit(f"unsupported DTYPE={dtype_str!r}; pick one of {sorted(dtype_map)}")
    dtype = dtype_map[dtype_str]

    log.info("loading tokenizer+model from %s on %s (%s)", model_path, device, dtype_str)
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=dtype,
        device_map=device,
        trust_remote_code=True,
    )
    model.eval()
    log.info("model loaded; MAX_NUM_SEQS=%d", max_num_seqs)

    # Concurrency primitive: a Lock when max_num_seqs==1 (strict serial, the
    # OOM-safe default), otherwise a bounded semaphore.
    if max_num_seqs == 1:
        _gate: Any = asyncio.Lock()
    else:
        _gate = asyncio.Semaphore(max_num_seqs)

    class ChatMessage(BaseModel):
        role: str
        content: str

    class ChatCompletionRequest(BaseModel):
        model: str = model_name
        messages: list[ChatMessage]
        max_tokens: int | None = None
        max_new_tokens: int | None = None  # transformers alias
        temperature: float | None = None
        top_p: float | None = None
        stream: bool = False

    app = FastAPI(title="agent-sandbox transformers serve", version="0.1.0")

    @app.get("/health")
    @app.get("/v1/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "model": model_name,
            "max_num_seqs": max_num_seqs,
            "device": device,
            "dtype": dtype_str,
        }

    @app.get("/v1/models")
    def list_models() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [
                {"id": model_name, "object": "model", "owned_by": "agent-sandbox"}
            ],
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(req: ChatCompletionRequest) -> dict[str, Any]:
        if req.stream:
            raise HTTPException(
                status_code=400,
                detail="streaming not supported by the minimal transformers serve path; "
                "use vLLM serve for SSE streaming.",
            )
        if not req.messages:
            raise HTTPException(status_code=400, detail="messages must be non-empty")

        prompt = tokenizer.apply_chat_template(
            [m.model_dump() for m in req.messages],
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": req.max_new_tokens or req.max_tokens or max_new_tokens_fallback,
        }
        if req.temperature is not None:
            gen_kwargs["temperature"] = float(req.temperature)
        if req.top_p is not None:
            gen_kwargs["top_p"] = float(req.top_p)

        async with _gate:
            # generation is a blocking CUDA call -> run in a worker thread so
            # the event loop stays responsive under concurrent requests.
            def _generate() -> str:
                with torch.inference_mode():
                    out = model.generate(**inputs, **gen_kwargs)
                new_tokens = out[0][inputs["input_ids"].shape[1]:]
                return tokenizer.decode(new_tokens, skip_special_tokens=True)

            content = await asyncio.to_thread(_generate)

        return {
            "id": f"chatcmpl-{model_name}",
            "object": "chat.completion",
            "model": req.model or model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": int(inputs["input_ids"].shape[1]),
                "completion_tokens": len(content),
                "total_tokens": int(inputs["input_ids"].shape[1]) + len(content),
            },
        }

    # stash bind info for the runner
    app.state.host = host  # type: ignore[attr-defined]
    app.state.port = port  # type: ignore[attr-defined]
    return app


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = _build_app()
    import uvicorn  # type: ignore

    uvicorn.run(
        app,
        host=app.state.host,
        port=app.state.port,
        log_level=os.environ.get("UVICORN_LOG_LEVEL", "info"),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
