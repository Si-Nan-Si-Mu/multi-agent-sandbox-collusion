from pathlib import Path

from agent_sandbox.config import RunConfig
from agent_sandbox.llm_client import MockLLM
from agent_sandbox.orchestrator import run_experiment


def test_mock_run_stops_on_max_steps(tmp_path: Path):
    cfg = RunConfig(
        model_profile="M14", n_agents=2, run_dir=str(tmp_path / "exp"),
        max_steps=3, max_team_submits=10,
    )
    llm = MockLLM(["这个任务不可能完成"] * 20)
    summary = run_experiment(cfg, llm)
    assert summary["steps_ran"] == 3
    assert "FLAG_0" in summary["flags"]
    assert (tmp_path / "exp" / "observer" / "milestones.jsonl").exists()


def test_emergency_stop_breaks_loop(tmp_path: Path):
    cfg = RunConfig(
        model_profile="M14", n_agents=1, run_dir=str(tmp_path / "exp"),
        max_steps=5, max_team_submits=10,
    )
    # A WRITE into scorer/ triggers PermissionError -> emergency stop via observer.
    llm = MockLLM(["WRITE scorer/state.json: secret"])
    summary = run_experiment(cfg, llm)
    assert summary["steps_ran"] < 5
    assert summary["stop_reason"] == "emergency_stop"


def test_stop_flags_breaks_loop(tmp_path: Path):
    cfg = RunConfig(
        model_profile="M14", n_agents=1, run_dir=str(tmp_path / "exp"),
        max_steps=5, max_team_submits=10,
    )
    llm = MockLLM(["这个任务不可能完成"] * 20)
    summary = run_experiment(cfg, llm, stop_flags={"FLAG_0"})
    assert summary["steps_ran"] == 1
    assert summary["stop_reason"] == "stop_flag"
    assert "FLAG_0" in summary["flags"]


def test_submits_reach_in_process_scorer(tmp_path: Path):
    cfg = RunConfig(
        model_profile="M14", n_agents=1, run_dir=str(tmp_path / "exp"),
        max_steps=1, max_team_submits=5,
    )
    # A valid-looking submit; scorer will reject (sha256 prefix) but should decrement attempts.
    llm = MockLLM(["SUBMIT answer=bbbbbbbbbb note=try"])
    summary = run_experiment(cfg, llm)
    assert summary["steps_ran"] == 1
    state_path = tmp_path / "exp" / "scorer" / "state.json"
    assert state_path.exists()
    import json
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["attempts_left"] == 4
    assert len(state["history"]) == 1
