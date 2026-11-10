from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from agent_sandbox.config import RunConfig
from agent_sandbox.llm_client import LLMClient
from agent_sandbox.roles import build_system_prompt
from agent_sandbox.workspace import assert_agent_path_allowed

_WRITE_RE = re.compile(r"^WRITE\s+([^:]+):\s?(.*)$")
_SUBMIT_RE = re.compile(r"^SUBMIT\s+answer=(.*?)\s+note=(.*)$")


@dataclass
class AgentActResult:
    text: str
    writes: list[tuple[str, str]]
    submit: dict | None


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def resolve_write_path(rel: str, run_dir: str, agent_id: str) -> Path:
    """Join a WRITE path onto the run directory.

    public/... and agents/... stay relative to run_dir.
    home/... is this agent's private home (agents/<id>/home/...).
    Any other relative path is also joined onto run_dir, then ACL decides.
    """
    raw = rel.strip().strip('"').strip("'")
    path = Path(raw)
    if path.is_absolute():
        return path
    normalized = raw.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    parts = tuple(part for part in normalized.split("/") if part not in ("", "."))
    if not parts:
        raise PermissionError("empty WRITE path")
    root = Path(run_dir)
    if parts[0] == "home":
        return root.joinpath("agents", agent_id, "home", *parts[1:])
    return root.joinpath(*parts)


class AgentRuntime:
    def __init__(self, cfg: RunConfig, agent_id: str, role: str, llm: LLMClient):
        self.cfg = cfg
        self.agent_id = agent_id
        self.role = role
        self.llm = llm

    def act(self, step: int) -> AgentActResult:
        messages = [
            {
                "role": "system",
                "content": build_system_prompt(self.role, self.cfg.safety_mode),
            },
            {"role": "user", "content": self._user_message(step)},
        ]
        text = self.llm.chat(messages)
        writes: list[tuple[str, str]] = []
        submit: dict | None = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            write_match = _WRITE_RE.match(line)
            if write_match:
                rel = write_match.group(1).strip()
                content = write_match.group(2)
                written = self._apply_write(rel, content)
                writes.append((str(written), content))
                continue
            submit_match = _SUBMIT_RE.match(line)
            if submit_match:
                submit = {
                    "answer": submit_match.group(1),
                    "note": submit_match.group(2),
                    "agent_id": self.agent_id,
                }
        return AgentActResult(text=text, writes=writes, submit=submit)

    def _user_message(self, step: int) -> str:
        root = Path(self.cfg.run_dir)
        brief_path = root / "public" / "tasks" / "brief.md"
        brief = (
            brief_path.read_text(encoding="utf-8")
            if brief_path.is_file()
            else "(no task brief)"
        )
        public_note = ""
        if not self.cfg.public_write:
            public_note = "Public writes are disabled. WRITE only under home/.\n"
        return (
            f"step={step}\n"
            f"agent_id={self.agent_id}\n"
            f"role={self.role}\n"
            f"{public_note}"
            f"Task brief:\n{brief}"
        )

    def _apply_write(self, rel: str, content: str) -> Path:
        target = resolve_write_path(rel, self.cfg.run_dir, self.agent_id)
        public = Path(self.cfg.run_dir) / "public"
        if not self.cfg.public_write and _is_within(target, public):
            raise PermissionError(f"public_write disabled: {rel}")
        assert_agent_path_allowed(self.agent_id, str(target), self.cfg.run_dir, "write")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target
