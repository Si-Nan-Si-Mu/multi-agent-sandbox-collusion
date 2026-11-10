"""Matrix JSON configs must load as RunConfig with the planned caps."""

import json
from pathlib import Path

import pytest

from agent_sandbox.config import RunConfig

ROOT = Path(__file__).resolve().parents[1]

# M14-N12/16 (fp16, max_num_seqs=2) and M32Q-N4/8 (INT4/AWQ, max_num_seqs=1).
EXPECTED = {
    "m14_n12.json": {
        "model_profile": "M14",
        "n_agents": 12,
        "max_num_seqs": 2,
        "model_name": "Qwen2.5-14B",
    },
    "m14_n16.json": {
        "model_profile": "M14",
        "n_agents": 16,
        "max_num_seqs": 2,
        "model_name": "Qwen2.5-14B",
    },
    "m32q_n4.json": {
        "model_profile": "M32Q",
        "n_agents": 4,
        "max_num_seqs": 1,
        "model_name": "Qwen2.5-32B-Instruct-AWQ",
    },
    "m32q_n8.json": {
        "model_profile": "M32Q",
        "n_agents": 8,
        "max_num_seqs": 1,
        "model_name": "Qwen2.5-32B-Instruct-AWQ",
    },
}


@pytest.mark.parametrize("name,expect", list(EXPECTED.items()))
def test_matrix_config_loads_as_runconfig(name, expect):
    path = ROOT / "configs" / name
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["model_profile"] == expect["model_profile"]
    assert data["n_agents"] == expect["n_agents"]
    assert data["max_num_seqs"] == expect["max_num_seqs"]
    assert data["model_name"] == expect["model_name"]
    cfg = RunConfig.model_validate(data)
    assert cfg.model_profile == expect["model_profile"]
    assert cfg.n_agents == expect["n_agents"]
    assert cfg.max_num_seqs == expect["max_num_seqs"]
    assert cfg.model_name == expect["model_name"]
    assert cfg.run_dir


ABLATIONS = {
    "ablation_nopublic_m14_n8.json": {
        "model_profile": "M14",
        "n_agents": 8,
        "max_num_seqs": 2,
        "model_name": "Qwen2.5-14B",
        "public_write": False,
        "safety_mode": "weak",
    },
    "ablation_strong_safety_m14_n8.json": {
        "model_profile": "M14",
        "n_agents": 8,
        "max_num_seqs": 2,
        "model_name": "Qwen2.5-14B",
        "public_write": True,
        "safety_mode": "strong",
    },
}


@pytest.mark.parametrize("name,expect", list(ABLATIONS.items()))
def test_ablation_config_sets_public_write_or_safety(name, expect):
    path = ROOT / "configs" / name
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["public_write"] is expect["public_write"]
    assert data["safety_mode"] == expect["safety_mode"]
    assert data["n_agents"] == 8
    assert data["model_profile"] == "M14"
    cfg = RunConfig.model_validate(data)
    assert cfg.public_write is expect["public_write"]
    assert cfg.safety_mode == expect["safety_mode"]
    assert cfg.n_agents == 8
    assert cfg.model_profile == "M14"
    assert cfg.max_num_seqs == expect["max_num_seqs"]
    assert cfg.model_name == expect["model_name"]
