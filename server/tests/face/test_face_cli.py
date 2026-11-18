"""F25 review: `postcare replay` đóng adapter pose kể cả khi tạo cổng face lỗi."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from postcare.cli import main as cli_main
from postcare.vision.inference import pose_mediapipe
from tests.replay.helpers import write_camera_yaml


class _ClosablePose:
    closed = False

    def close(self) -> None:
        self.closed = True


def test_replay_closes_pose_adapter_when_face_gate_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pose = _ClosablePose()

    def fake_from_config(*_args: Any, **_kwargs: Any) -> _ClosablePose:
        return pose

    def broken_face_gate(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("face gate hỏng")

    monkeypatch.setattr(
        pose_mediapipe.MediaPipePoseAdapter, "from_config", staticmethod(fake_from_config)
    )
    monkeypatch.setattr(cli_main, "_face_gate", broken_face_gate)
    video = tmp_path / "clip.avi"
    video.write_bytes(b"")
    result = CliRunner().invoke(
        cli_main.app,
        [
            "replay",
            "--video",
            str(video),
            "--camera-config",
            str(write_camera_yaml(tmp_path / "cam.yaml")),
            "--out",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code != 0
    assert pose.closed
