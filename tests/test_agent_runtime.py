from pathlib import Path

import pytest

from agent_sandbox.agent_runtime import AgentRuntime
from agent_sandbox.config import RunConfig, select_roles
from agent_sandbox.llm_client import MockLLM
from agent_sandbox.workspace import agent_id_for, prepare_run_dirs


def _agent(tmp_path: Path, reply: str, **cfg_kw):
    cfg = RunConfig(model_profile="M14", n_agents=1, run_dir=str(tmp_path / "r"), **cfg_kw)
    roles = select_roles(1, 1)
    prepare_run_dirs(cfg, roles)
    aid = agent_id_for(1, roles[0])
    llm = MockLLM([reply])
    return cfg, aid, AgentRuntime(cfg, aid, roles[0], llm)


def test_agent_writes_only_allowed(tmp_path: Path):
    cfg = RunConfig(model_profile="M14", n_agents=1, run_dir=str(tmp_path / "r"))
    roles = select_roles(1, 1)
    prepare_run_dirs(cfg, roles)
    aid = agent_id_for(1, roles[0])
    llm = MockLLM([
        "THOUGHT: try\nWRITE public/scratch/hi.txt: hello\nSUBMIT answer=bbbbbbbbbb note=test"
    ])
    agent = AgentRuntime(cfg, aid, roles[0], llm)
    result = agent.act(step=1)
    assert (tmp_path / "r" / "public" / "scratch" / "hi.txt").read_text(encoding="utf-8") == "hello"
    assert result.submit is not None
    assert result.submit["answer"] == "bbbbbbbbbb"
    assert result.submit["note"] == "test"
    assert result.text.startswith("THOUGHT:")


def test_write_under_home_and_colon_content(tmp_path: Path):
    cfg = RunConfig(model_profile="M14", n_agents=1, run_dir=str(tmp_path / "r"))
    roles = select_roles(1, 1)
    prepare_run_dirs(cfg, roles)
    aid = agent_id_for(1, roles[0])
    reply = (
        f"WRITE agents/{aid}/home/notes/idea.txt: a:b\n"
        "WRITE home/ok.txt: yes"
    )
    agent = AgentRuntime(cfg, aid, roles[0], MockLLM([reply]))
    result = agent.act(step=2)
    root = tmp_path / "r" / "agents" / aid / "home"
    assert (root / "notes" / "idea.txt").read_text(encoding="utf-8") == "a:b"
    assert (root / "ok.txt").read_text(encoding="utf-8") == "yes"
    assert result.submit is None
    assert len(result.writes) == 2


def test_natural_language_has_no_actions(tmp_path: Path):
    _cfg, _aid, agent = _agent(tmp_path, "这个任务不可能完成")
    result = agent.act(step=1)
    assert result.text == "这个任务不可能完成"
    assert result.writes == []
    assert result.submit is None


def test_scorer_write_is_denied(tmp_path: Path):
    _cfg, _aid, agent = _agent(tmp_path, "WRITE scorer/state.json: secret")
    with pytest.raises(PermissionError):
        agent.act(step=1)
    assert not (tmp_path / "r" / "scorer" / "state.json").exists()


def test_public_write_disabled(tmp_path: Path):
    _cfg, aid, agent = _agent(
        tmp_path,
        "WRITE public/scratch/hi.txt: hello\nWRITE home/local.txt: keep",
        public_write=False,
    )
    with pytest.raises(PermissionError, match="public_write disabled"):
        agent.act(step=1)
    assert not (tmp_path / "r" / "public" / "scratch" / "hi.txt").exists()
    assert not (tmp_path / "r" / "agents" / aid / "home" / "local.txt").exists()
