"""Plot step vs cumulative FLAG_* awards for one run directory.

Usage:
    python scripts/plot_flag_timeline.py --run-dir runs/demo --out runs/demo/flag_timeline.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_sandbox.metrics import load_milestones, timeline_rows


def plot_flag_timeline(run_dir: Path | str, out_path: Path | str) -> Path:
    steps = [0]
    counts = [0]
    labels: list[str] = []
    last = 0
    for row in timeline_rows(load_milestones(run_dir)):
        count = int(row["cumulative_flags"])
        if count == last or not str(row["flag"]).startswith("FLAG_"):
            continue
        last = count
        steps.append(int(row["step"]))
        counts.append(count)
        labels.append(str(row["flag"]))

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.step(steps, counts, where="post", color="#1f4e79", linewidth=2)
    if labels:
        ax.plot(steps[1:], counts[1:], "o", color="#c45911")
        for step, count, label in zip(steps[1:], counts[1:], labels):
            ax.annotate(
                label,
                (step, count),
                textcoords="offset points",
                xytext=(6, 6),
                fontsize=8,
            )
    ax.set_xlabel("step")
    ax.set_ylabel("cumulative flags")
    ax.set_title("Flag timeline")
    ax.set_ylim(bottom=0)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot step vs cumulative flags")
    parser.add_argument("--run-dir", required=True, help="Run directory containing observer/milestones.jsonl")
    parser.add_argument("--out", required=True, help="Output image path (.png)")
    args = parser.parse_args()
    plot_flag_timeline(args.run_dir, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
