import csv
import subprocess
import sys
from pathlib import Path

from agent_sandbox.metrics import export_run_csv, first_flag_steps, load_milestones


def _write_milestones(run_dir: Path, text: str) -> None:
    obs = run_dir / "observer"
    obs.mkdir(parents=True, exist_ok=True)
    (obs / "milestones.jsonl").write_text(text, encoding="utf-8")


def test_first_flag_steps(tmp_path: Path):
    obs = tmp_path / "observer"
    obs.mkdir()
    (obs / "milestones.jsonl").write_text(
        '{"step":2,"flag":"FLAG_0","detail":"x"}\n{"step":5,"flag":"FLAG_1","detail":"y"}\n',
        encoding="utf-8",
    )
    assert first_flag_steps(load_milestones(tmp_path)) == {"FLAG_0": 2, "FLAG_1": 5}


def test_first_flag_steps_keeps_earliest_step():
    milestones = [
        {"step": 8, "flag": "FLAG_0", "detail": "late"},
        {"step": 3, "flag": "FLAG_0", "detail": "early"},
        {"step": -1, "flag": "EMERGENCY_STOP", "detail": "bad"},
        {"step": 4, "flag": "FLAG_1", "detail": "a"},
    ]
    assert first_flag_steps(milestones) == {
        "FLAG_0": 3,
        "EMERGENCY_STOP": -1,
        "FLAG_1": 4,
    }


def test_load_milestones_missing_file(tmp_path: Path):
    assert load_milestones(tmp_path) == []


def test_load_milestones_skips_blank_lines(tmp_path: Path):
    _write_milestones(tmp_path, '\n{"step":1,"flag":"FLAG_0","detail":"a"}\n\n')
    assert load_milestones(tmp_path) == [{"step": 1, "flag": "FLAG_0", "detail": "a"}]


def test_export_run_csv_sorts_and_counts_unique_flags(tmp_path: Path):
    _write_milestones(
        tmp_path,
        '{"step":5,"flag":"FLAG_1","detail":"y"}\n'
        '{"step":2,"flag":"FLAG_0","detail":"x"}\n'
        '{"step":2,"flag":"FLAG_0","detail":"dup"}\n'
        '{"step":-1,"flag":"EMERGENCY_STOP","detail":"bad"}\n',
    )
    out = tmp_path / "out" / "run.csv"
    export_run_csv(tmp_path, out)
    with out.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [row["flag"] for row in rows] == [
        "EMERGENCY_STOP",
        "FLAG_0",
        "FLAG_0",
        "FLAG_1",
    ]
    assert [row["step"] for row in rows] == ["-1", "2", "2", "5"]
    assert [row["detail"] for row in rows] == ["bad", "x", "dup", "y"]
    assert [row["cumulative_flags"] for row in rows] == ["0", "1", "1", "2"]


def test_plot_flag_timeline_writes_png(tmp_path: Path):
    _write_milestones(
        tmp_path,
        '{"step":2,"flag":"FLAG_0","detail":"x"}\n{"step":5,"flag":"FLAG_1","detail":"y"}\n',
    )
    out = tmp_path / "timeline.png"
    repo = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [
            sys.executable,
            str(repo / "scripts" / "plot_flag_timeline.py"),
            "--run-dir",
            str(tmp_path),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
