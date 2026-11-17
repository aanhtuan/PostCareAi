"""F05 AC4: lệnh `postcare probe --source …` (CliRunner của Typer, video tổng hợp)."""

from pathlib import Path

from typer.testing import CliRunner

from postcare.cli.main import app
from tests.camera.synthetic import write_video

runner = CliRunner()


def test_probe_on_file_prints_stats(tmp_path: Path) -> None:
    video = write_video(tmp_path / "clip.avi", n_frames=30, fps=30, size=(64, 48))
    result = runner.invoke(app, ["probe", "--source", str(video), "--seconds", "5"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "FILE" in out
    assert "64x48" in out
    assert "Số khung đã xử lý: 15" in out
    assert "Số khung bỏ: 15" in out
    assert "FPS" in out
    assert "Số lần mất kết nối: 0" in out


def test_probe_respects_max_fps(tmp_path: Path) -> None:
    video = write_video(tmp_path / "clip.avi", n_frames=30, fps=30)
    result = runner.invoke(app, ["probe", "--source", str(video), "--max-fps", "30"])
    assert result.exit_code == 0, result.output
    assert "Số khung bỏ: 0" in result.output


def test_probe_bad_source_exits_nonzero(tmp_path: Path) -> None:
    result = runner.invoke(app, ["probe", "--source", str(tmp_path / "khong-co.mp4")])
    assert result.exit_code != 0
    assert "Không mở được nguồn" in result.output
