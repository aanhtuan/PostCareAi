"""F31 R4 (AC4): lệnh `postcare workers` (dựng lệnh cho từng camera; `--dry-run` không chạy gì)."""

import sys
from pathlib import Path

from typer.testing import CliRunner

from postcare.cli.main import app

runner = CliRunner()


def test_dry_run_prints_one_command_per_camera(tmp_path: Path) -> None:
    clip = tmp_path / "a02.mp4"
    clip.write_bytes(b"")
    result = runner.invoke(
        app,
        [
            "workers",
            "--camera-id",
            "1",
            "--camera-id",
            "2",
            "--video",
            f"2={clip}",
            "--model",
            "full",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.output.splitlines() if "--camera-id" in ln]
    assert len(lines) == 2
    assert "--camera-id 1" in lines[0] and "--video" not in lines[0]
    assert "--camera-id 2" in lines[1] and str(clip) in lines[1]
    assert all("--model full" in ln for ln in lines)
    assert all(Path(sys.executable).name in ln for ln in lines)


def test_video_for_unknown_camera_fails(tmp_path: Path) -> None:
    clip = tmp_path / "a03.mp4"
    clip.write_bytes(b"")
    result = runner.invoke(
        app, ["workers", "--camera-id", "1", "--video", f"3={clip}", "--dry-run"]
    )
    assert result.exit_code != 0


def test_missing_video_file_fails(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["workers", "--camera-id", "1", "--video", f"1={tmp_path / 'none.mp4'}", "--dry-run"],
    )
    assert result.exit_code == 2
