from pathlib import Path
import pytest
from agent_sandbox.config import RunConfig, select_roles
from agent_sandbox.workspace import prepare_run_dirs, assert_agent_path_allowed

def test_prepare_run_dirs(tmp_path: Path):
    cfg = RunConfig(model_profile="M14", n_agents=2, run_dir=str(tmp_path / "r1"))
    roles = select_roles(2, seed=1)
    paths = prepare_run_dirs(cfg, roles)
    assert (tmp_path / "r1" / "public" / "tasks").is_dir()
    assert (tmp_path / "r1" / "scorer").is_dir()
    assert (tmp_path / "r1" / "config.json").is_file()
    assert len(paths["agent_homes"]) == 2

def test_agent_cannot_read_scorer(tmp_path: Path):
    cfg = RunConfig(model_profile="M14", n_agents=1, run_dir=str(tmp_path / "r2"))
    roles = select_roles(1, 1)
    prepare_run_dirs(cfg, roles)
    aid = "A01_planner"
    with pytest.raises(PermissionError):
        assert_agent_path_allowed(aid, str(tmp_path / "r2" / "scorer" / "state.json"), cfg.run_dir, "read")

def test_agent_can_write_public_and_home(tmp_path: Path):
    cfg = RunConfig(model_profile="M14", n_agents=1, run_dir=str(tmp_path / "r3"))
    prepare_run_dirs(cfg, select_roles(1, 1))
    aid = "A01_planner"
    assert_agent_path_allowed(aid, str(tmp_path / "r3" / "public" / "scratch" / "x.txt"), cfg.run_dir, "write")
    assert_agent_path_allowed(aid, str(tmp_path / "r3" / "agents" / aid / "home" / "note.txt"), cfg.run_dir, "write")

def test_public_prefix_sibling_is_denied(tmp_path: Path):
    cfg = RunConfig(model_profile="M14", n_agents=1, run_dir=str(tmp_path / "r4"))
    prepare_run_dirs(cfg, select_roles(1, 1))
    aid = "A01_planner"
    with pytest.raises(PermissionError):
        assert_agent_path_allowed(
            aid, str(tmp_path / "r4" / "public_extra" / "x.txt"), cfg.run_dir, "write"
        )
    assert_agent_path_allowed(
        aid, str(tmp_path / "r4" / "public" / "scratch" / "x.txt"), cfg.run_dir, "write"
    )
