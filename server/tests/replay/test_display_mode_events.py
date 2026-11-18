"""F28 AC4, R8, R9: chế độ hiển thị không đổi sự kiện; `replay --display-mode`."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from postcare.cli.main import app
from postcare.replay.camera_config import load_camera_config
from postcare.replay.runner import replay_video
from postcare.schemas.enums import DisplayMode
from tests.replay.helpers import (
    DEFAULT_ENGINE,
    fake_source_and_adapter,
    scenario,
    write_camera_yaml,
)

SIZE = (160, 120)


def test_display_mode_does_not_change_events(tmp_path: Path) -> None:
    camera = load_camera_config(write_camera_yaml(tmp_path / "cam.yaml"))
    config = camera.engine_config(DEFAULT_ENGINE)
    observations = scenario()
    results: dict[DisplayMode, tuple[str, str]] = {}
    for mode in DisplayMode:
        source, adapter = fake_source_and_adapter(observations, size=SIZE)
        out = tmp_path / mode.value
        summary = replay_video(
            source, adapter, camera, config, out, preview=True, display_mode=mode
        )
        assert (out / "preview.mp4").is_file()
        assert summary.run["display_mode"] == mode.value
        results[mode] = (
            (out / "events.jsonl").read_text(encoding="utf-8"),
            (out / "frames.jsonl").read_text(encoding="utf-8"),
        )
    events = {r[0] for r in results.values()}
    frames = {r[1] for r in results.values()}
    assert len(events) == 1 and len(frames) == 1
    assert next(iter(events)).strip(), "kịch bản phải có sự kiện để so sánh có ý nghĩa"


def test_replay_default_display_mode_is_blur(tmp_path: Path) -> None:
    camera = load_camera_config(write_camera_yaml(tmp_path / "cam.yaml"))
    source, adapter = fake_source_and_adapter(scenario()[:5], size=SIZE)
    summary = replay_video(
        source, adapter, camera, camera.engine_config(DEFAULT_ENGINE), tmp_path / "o", preview=True
    )
    assert summary.run["display_mode"] == "BLUR"


def test_cli_rejects_unknown_display_mode(tmp_path: Path) -> None:
    cam = write_camera_yaml(tmp_path / "cam.yaml")
    args = ["replay", "--video", str(tmp_path / "x.mp4"), "--camera-config", str(cam)]
    result = CliRunner().invoke(
        app, [*args, "--out", str(tmp_path / "o"), "--preview", "--display-mode", "FOO"]
    )
    assert result.exit_code != 0
    assert "--display-mode" in result.output


@pytest.mark.parametrize("mode", ["RAW", "BLUR", "SKELETON"])
def test_cli_accepts_display_mode_option(tmp_path: Path, mode: str) -> None:
    """Giá trị hợp lệ qua được bước parse (dừng ở chỗ thiếu model/video, không phải tùy chọn)."""
    cam = write_camera_yaml(tmp_path / "cam.yaml")
    args = ["replay", "--video", str(tmp_path / "x.mp4"), "--camera-config", str(cam)]
    result = CliRunner().invoke(
        app,
        [
            *args,
            "--out",
            str(tmp_path / "o"),
            "--preview",
            "--display-mode",
            mode,
            "--models-dir",
            str(tmp_path / "no-models"),
        ],
    )
    assert "--display-mode" not in result.output
    assert "No such option" not in result.output
