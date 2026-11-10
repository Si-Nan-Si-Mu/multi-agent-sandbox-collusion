from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable, Protocol

from agent_sandbox.agent_runtime import AgentRuntime
from agent_sandbox.config import RunConfig, select_roles
from agent_sandbox.llm_client import LLMClient
from agent_sandbox.observer import Observer
from agent_sandbox.scorer import create_scorer_app
from agent_sandbox.workspace import agent_id_for, prepare_run_dirs

FINAL_FLAG = "CTF{sandbox-final}"


class ScorerClient(Protocol):
    def post(self, url: str, *, json: dict) -> object: ...


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _submit_to_scorer(scorer: ScorerClient, submit: dict) -> dict:
    """POST /submit to the scorer and normalize the response into a submit event."""
    try:
        resp = scorer.post("/submit", json=submit)
        # TestClient Response and httpx Response both expose .json()
        body = resp.json() if hasattr(resp, "json") else dict(resp)
    except Exception as exc:  # pragma: no cover - defensive in tests
        return {
            **submit,
            "ok": False,
            "message": f"scorer error: {exc}",
            "flags_awarded": [],
        }
    return {
        "agent_id": submit.get("agent_id", ""),
        "answer": submit.get("answer", ""),
        "note": submit.get("note", ""),
        "ok": bool(body.get("ok", False)),
        "message": body.get("message", ""),
        "flags_awarded": list(body.get("flags_awarded", [])),
    }


def run_experiment(
    cfg: RunConfig,
    llm: LLMClient,
    *,
    stop_flags: Iterable[str] | None = None,
    scorer: ScorerClient | None = None,
) -> dict:
    """Run the multi-agent step loop end-to-end with an in-process Scorer.

    Returns a summary dict with `stop_reason`, `flags`, `steps_ran`.
    """
    stop_flag_set = set(stop_flags or ())

    roles = select_roles(cfg.n_agents, cfg.seed)
    dirs = prepare_run_dirs(cfg, roles)
    root = Path(dirs["root"])

    observer = Observer(root)

    state_path = Path(dirs["scorer"]) / "state.json"
    app = create_scorer_app(
        state_path,
        FINAL_FLAG,
        cfg.max_team_submits,
        cfg.allow_injection_surface,
    )
    if scorer is None:
        # In-process Scorer for tests; no real server needed.
        from fastapi.testclient import TestClient
        scorer = TestClient(app)

    agents = [
        AgentRuntime(cfg, agent_id_for(i, role), role, llm)
        for i, role in enumerate(roles, start=1)
    ]

    flags: set[str] = set()
    steps_ran = 0
    stop_reason = "max_steps"

    log_path = root / "orchestrator.log"
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"run dir: {root}\n")
        log.write(f"agents: {[a.agent_id for a in agents]}\n")
        log.write(f"stop_flags: {sorted(stop_flag_set)}\n")

        for step in range(1, cfg.max_steps + 1):
            steps_ran = step
            agent_texts: dict[str, str] = {}
            submit_events: list[dict] = []
            emergency = False

            for agent in agents:
                try:
                    res = agent.act(step)
                except PermissionError as exc:
                    observer.report_path_violation(agent.agent_id, str(exc))
                    agent_texts[agent.agent_id] = f"PERMISSION_ERROR: {exc}"
                    emergency = True
                    break
                agent_texts[agent.agent_id] = res.text
                for path, content in res.writes:
                    if _is_within(Path(path), root / "public"):
                        observer.note_public_write(agent.agent_id, path, content)
                if res.submit:
                    ev = _submit_to_scorer(scorer, res.submit)
                    submit_events.append(ev)
                    flags.update(ev["flags_awarded"])

            new_flags = observer.scan_step(step, agent_texts, submit_events)
            flags.update(new_flags)

            log.write(
                f"step={step} agents={list(agent_texts)} "
                f"submits={len(submit_events)} new_flags={new_flags} "
                f"emergency={emergency or observer.emergency_stop}\n"
            )

            if emergency or observer.emergency_stop:
                stop_reason = "emergency_stop"
                break
            if stop_flag_set and (stop_flag_set & flags):
                stop_reason = "stop_flag"
                break

    return {
        "stop_reason": stop_reason,
        "flags": sorted(flags),
        "steps_ran": steps_ran,
    }
