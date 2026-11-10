"""pack_run.sh archives one run directory and leaves model weights out."""

from __future__ import annotations

import os
import subprocess
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "pack_run.sh"


def bash_exe() -> str:
    """Prefer Git Bash. System32 bash.exe is a WSL relay and is not a shell."""
    override = os.environ.get("PACK_TEST_BASH")
    candidates = [
        override,
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return "bash"


def to_bash(path: Path) -> str:
    """Git Bash on Windows does not accept drive-letter paths from pytest."""
    posix = path.resolve().as_posix()
    if os.name == "nt" and len(posix) >= 2 and posix[1] == ":":
        return "/" + posix[0].lower() + posix[2:]
    return posix


def _run(run_id: str, runs_root: Path, pack_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["RUNS_ROOT"] = to_bash(runs_root)
    env["PACK_DIR"] = to_bash(pack_dir)
    # cwd and the script path stay Windows paths so CreateProcess can start
    # Git Bash. RUNS_ROOT and PACK_DIR are bash paths because the script
    # passes them to tar inside bash.
    return subprocess.run(
        [bash_exe(), str(SCRIPT), run_id],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _names(archive: Path) -> set[str]:
    with tarfile.open(archive, "r:gz") as handle:
        return {name.replace("\\", "/") for name in handle.getnames()}


def test_pack_run_keeps_logs_and_drops_weights(tmp_path: Path):
    run_id = "m14_n12_seed1"
    run = tmp_path / "runs" / run_id
    (run / "observer").mkdir(parents=True)
    (run / "observer" / "milestones.jsonl").write_text(
        '{"step": 2, "flag": "FLAG_0", "detail": "x"}\n',
        encoding="utf-8",
    )
    (run / "public" / "tasks").mkdir(parents=True)
    (run / "public" / "tasks" / "brief.md").write_text("# task\n", encoding="utf-8")
    (run / "config.json").write_text("{}\n", encoding="utf-8")
    (run / "models").mkdir()
    (run / "models" / "model.safetensors").write_bytes(b"weight")
    (run / "models" / "config.json").write_text("{}\n", encoding="utf-8")
    (run / "weights").mkdir()
    (run / "weights" / "model.gguf").write_bytes(b"gguf")
    (run / "checkpoint.pt").write_bytes(b"pt")
    (run / "adapter.pth").write_bytes(b"pth")
    (run / "leak.bin").write_bytes(b"bin")

    pack_dir = tmp_path / "packs"
    proc = _run(run_id, tmp_path / "runs", pack_dir)

    assert proc.returncode == 0, proc.stderr
    archive = pack_dir / f"{run_id}.tar.gz"
    assert archive.is_file()
    names = _names(archive)
    assert f"{run_id}/observer/milestones.jsonl" in names
    assert f"{run_id}/public/tasks/brief.md" in names
    assert f"{run_id}/config.json" in names
    assert not any(
        name.endswith((".bin", ".safetensors", ".gguf", ".pt", ".pth"))
        for name in names
    )
    assert not any(
        "/models/" in name or name.endswith("/models")
        or "/weights/" in name or name.endswith("/weights")
        for name in names
    )


def test_pack_run_rejects_missing_directory(tmp_path: Path):
    proc = _run("missing_run", tmp_path / "runs", tmp_path / "packs")
    assert proc.returncode != 0
    assert "run directory not found" in proc.stderr
    assert not (tmp_path / "packs" / "missing_run.tar.gz").exists()


def test_pack_run_rejects_path_traversal(tmp_path: Path):
    proc = _run("../outside", tmp_path / "runs", tmp_path / "packs")
    assert proc.returncode != 0
    assert "run id must be a single directory name" in proc.stderr
    assert list((tmp_path / "packs").glob("*.tar.gz")) == []
