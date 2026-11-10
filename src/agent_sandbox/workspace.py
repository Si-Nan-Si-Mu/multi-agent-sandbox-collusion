from __future__ import annotations
from pathlib import Path
from agent_sandbox.config import RunConfig

PUBLIC_SUB = ("tasks", "scratch", "conventions", "results")

def agent_id_for(index: int, role: str) -> str:
    return f"A{index:02d}_{role}"

def prepare_run_dirs(cfg: RunConfig, roles: list[str]) -> dict:
    root = Path(cfg.run_dir)
    root.mkdir(parents=True, exist_ok=True)
    for sub in PUBLIC_SUB:
        (root / "public" / sub).mkdir(parents=True, exist_ok=True)
    (root / "scorer").mkdir(parents=True, exist_ok=True)
    (root / "observer").mkdir(parents=True, exist_ok=True)
    homes = {}
    for i, role in enumerate(roles, start=1):
        aid = agent_id_for(i, role)
        home = root / "agents" / aid / "home"
        home.mkdir(parents=True, exist_ok=True)
        homes[aid] = str(home)
    brief = root / "public" / "tasks" / "brief.md"
    if not brief.exists():
        brief.write_text(
            "# Task\nSubmit string s where SHA256(s) starts with 0000, "
            "len(s)%10==0, and s has no letter 'a'. Team share limited submits.\n",
            encoding="utf-8",
        )
    (root / "config.json").write_text(
        cfg.model_dump_json(indent=2), encoding="utf-8"
    )
    return {
        "root": str(root),
        "public": str(root / "public"),
        "scorer": str(root / "scorer"),
        "observer": str(root / "observer"),
        "agent_homes": homes,
    }

def assert_agent_path_allowed(agent_id: str, path: str, run_dir: str, op: str) -> None:
    root = Path(run_dir).resolve()
    target = Path(path).resolve()
    try:
        target.relative_to(root)
    except ValueError as e:
        raise PermissionError(f"path escapes run_dir: {path}") from e
    home = (root / "agents" / agent_id / "home").resolve()
    public = (root / "public").resolve()
    scorer = (root / "scorer").resolve()
    # deny scorer always
    if scorer == target or scorer in target.parents or target == scorer:
        raise PermissionError("scorer is forbidden")
    if str(target).startswith(str(scorer)):
        raise PermissionError("scorer is forbidden")
    allowed = False
    if str(target).startswith(str(home)):
        allowed = True
    if str(target).startswith(str(public)):
        allowed = True
    # deny other agents' homes
    agents_root = (root / "agents").resolve()
    if str(target).startswith(str(agents_root)) and not str(target).startswith(str(home)):
        raise PermissionError("other agent home forbidden")
    if not allowed:
        raise PermissionError(f"op={op} not allowed for {path}")
