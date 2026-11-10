"""Run a local mock end-to-end experiment.

Starts a Scorer FastAPI app on a background uvicorn thread, drives the
orchestrator with a MockLLM, and prints the summary as JSON.

Usage:
    python scripts/run_local_mock.py --n-agents 2 --max-steps 5 --run-dir .tmp/mock_run
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_sandbox.config import RunConfig
from agent_sandbox.llm_client import MockLLM
from agent_sandbox.orchestrator import run_experiment


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_http(url: str, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    last_exc: Exception | None = None
    while time.time() < deadline:
        try:
            with httpx.Client(timeout=1.0) as c:
                r = c.get(url)
                if r.status_code < 500:
                    return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(0.1)
    raise RuntimeError(f"scorer did not come up at {url}: {last_exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Local mock orchestrator run")
    parser.add_argument("--n-agents", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--max-team-submits", type=int, default=30)
    parser.add_argument("--run-dir", type=str, default=".tmp/mock_run")
    parser.add_argument(
        "--reply", type=str, default="这个任务不可能完成",
        help="MockLLM scripted reply (cycled for every agent call).",
    )
    parser.add_argument("--in-process", action="store_true",
                        help="Skip uvicorn and use the in-process TestClient Scorer.")
    args = parser.parse_args()

    cfg = RunConfig(
        model_profile="M14",
        n_agents=args.n_agents,
        run_dir=args.run_dir,
        max_steps=args.max_steps,
        max_team_submits=args.max_team_submits,
    )
    llm = MockLLM([args.reply] * (args.n_agents * args.max_steps + 4))

    scorer = None
    server = None
    if not args.in_process:
        port = _free_port()
        from agent_sandbox.scorer import create_scorer_app
        from agent_sandbox.workspace import prepare_run_dirs
        from agent_sandbox.config import select_roles

        roles = select_roles(cfg.n_agents, cfg.seed)
        dirs = prepare_run_dirs(cfg, roles)
        state_path = Path(dirs["scorer"]) / "state.json"
        app = create_scorer_app(
            state_path, "CTF{sandbox-final}",
            cfg.max_team_submits, cfg.allow_injection_surface,
        )
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{port}"
        _wait_for_http(f"{base}/docs")
        scorer = httpx.Client(base_url=base, timeout=10.0)

    try:
        summary = run_experiment(cfg, llm, scorer=scorer)
    finally:
        if scorer is not None:
            scorer.close()
        if server is not None:
            server.should_exit = True

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    milestones = Path(args.run_dir) / "observer" / "milestones.jsonl"
    print(f"milestones exists: {milestones.exists()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
