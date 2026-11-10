"""Parse a run directory into flag timelines and CSV tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def load_milestones(run_dir: Path | str) -> list[dict]:
    path = Path(run_dir) / "observer" / "milestones.jsonl"
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def first_flag_steps(milestones: list[dict]) -> dict[str, int]:
    """Earliest step for each flag name, including EMERGENCY_STOP."""
    earliest: dict[str, int] = {}
    for row in milestones:
        flag = row.get("flag")
        if not flag or "step" not in row:
            continue
        step = int(row["step"])
        if flag not in earliest or step < earliest[flag]:
            earliest[flag] = step
    return earliest


def timeline_rows(milestones: list[dict]) -> list[dict]:
    """Milestones ordered by step, with a running count of distinct FLAG_* awards.

    EMERGENCY_STOP and repeated flags do not increase cumulative_flags.
    """
    ordered = sorted(
        enumerate(milestones),
        key=lambda pair: (int(pair[1].get("step", 0)), pair[0]),
    )
    seen: set[str] = set()
    cumulative = 0
    rows: list[dict] = []
    for _, row in ordered:
        flag = str(row.get("flag", ""))
        if flag.startswith("FLAG_") and flag not in seen:
            seen.add(flag)
            cumulative += 1
        rows.append(
            {
                "step": row.get("step", ""),
                "flag": flag,
                "detail": row.get("detail", ""),
                "cumulative_flags": cumulative,
            }
        )
    return rows


def export_run_csv(run_dir: Path | str, out_csv: Path | str) -> Path:
    out = Path(out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["step", "flag", "detail", "cumulative_flags"]
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(timeline_rows(load_milestones(run_dir)))
    return out
