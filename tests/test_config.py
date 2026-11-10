from agent_sandbox.config import ROLE_POOL, RunConfig, select_roles


def test_role_pool_has_eight_base_roles():
    assert ROLE_POOL == [
        "planner", "solver", "critic", "scribe",
        "scout", "advocate", "risk_taker", "coordinator",
    ]


def test_select_roles_n16_is_deterministic():
    a = select_roles(16, seed=7)
    b = select_roles(16, seed=7)
    assert a == b
    assert len(a) == 16
    assert a[:8] == ROLE_POOL
    assert a[8] == "planner_2"


def test_runconfig_defaults():
    cfg = RunConfig(model_profile="M14", n_agents=12, run_dir="/tmp/r")
    assert cfg.max_steps == 40
    assert cfg.max_team_submits == 30
    assert cfg.allow_injection_surface is False
    assert cfg.max_num_seqs == 2
