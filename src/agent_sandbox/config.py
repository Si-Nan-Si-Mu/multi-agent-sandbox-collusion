from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, model_validator

ROLE_POOL = [
    "planner", "solver", "critic", "scribe",
    "scout", "advocate", "risk_taker", "coordinator",
]


class RunConfig(BaseModel):
    model_profile: str  # "M14" | "M32Q"
    n_agents: int
    run_dir: str
    seed: int = 7
    max_steps: int = 40
    max_team_submits: int = 30
    allow_injection_surface: bool = False
    max_num_seqs: int = 2
    max_tokens: int = 768
    context_tokens: int = 4096
    public_write: bool = True
    safety_mode: str = "weak"  # "weak" | "strong" | "none"
    llm_base_url: str = "http://127.0.0.1:8001/v1"
    scorer_url: str = "http://127.0.0.1:8002"
    model_name: str = "Qwen2.5-14B"

    @model_validator(mode="after")
    def _caps(self):
        if self.model_profile == "M32Q" and self.max_num_seqs > 1:
            object.__setattr__(self, "max_num_seqs", 1)
        if self.model_profile == "M14" and self.max_num_seqs not in (1, 2):
            object.__setattr__(self, "max_num_seqs", 2)
        return self


def select_roles(n: int, seed: int) -> list[str]:
    """Ignore seed for order (fixed pool order); seed reserved for future shuffle flag."""
    _ = seed
    out: list[str] = []
    copy_idx = 1
    while len(out) < n:
        for role in ROLE_POOL:
            if copy_idx == 1:
                out.append(role)
            else:
                out.append(f"{role}_{copy_idx}")
            if len(out) >= n:
                return out
        copy_idx += 1
    return out


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
