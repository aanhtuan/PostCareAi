"""F12 AC3: `--preview` ghi preview.mp4 có skeleton, ROI, trạng thái (khung tổng hợp)."""

from pathlib import Path

import cv2
import numpy as np
from postcare.replay.camera_config import load_camera_config
from postcare.replay.runner import replay_video
from postcare.vision.render import draw_debug_overlay
from typer.testing import CliRunner

from postcare.cli.main import app
from postcare.schemas.enums import ObservationQuality, Priority
from postcare.schemas.events import EngineEvent, EventCode
from postcare.schemas.state import (
    ActivityLevel,
    BodyState,
    BodyStateSnapshot,
    FaceSignals,
    FaceStatus,
    RestStatus,
)
from tests.engine.builders import BED_ROI
from tests.replay.helpers import (
    DEFAULT_ENGINE,
    fake_source_and_adapter,
    scenario,
    write_camera_yaml,
    write_observations,
)

SIZE = (320, 180)


def test_preview_writes_mp4(tmp_path: Path) -> None:
    camera = load_camera_config(write_camera_yaml(tmp_path / "cam.yaml"))
    observations = scenario()
    source, adapter = fake_source_and_adapter(observations, size=SIZE)
    out = tmp_path / "run"
    replay_video(source, adapter, camera, camera.engine_config(DEFAULT_ENGINE), out, preview=True)
    preview = out / "preview.mp4"
    assert preview.is_file()
    cap = cv2.VideoCapture(str(preview))
    try:
        assert cap.isOpened()
        assert int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) == SIZE[0]
        assert int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) == SIZE[1]
        count = 0
        while True:
            ok, _ = cap.read()
            if not ok:
                break
            count += 1
    finally:
        cap.release()
    assert count == len(observations)


def test_no_preview_flag_writes_no_mp4(tmp_path: Path) -> None:
    camera = load_camera_config(write_camera_yaml(tmp_path / "cam.yaml"))
    source, adapter = fake_source_and_adapter(scenario()[:10], size=SIZE)
    out = tmp_path / "run"
    replay_video(source, adapter, camera, camera.engine_config(DEFAULT_ENGINE), out)
    assert not list(out.glob("*.mp4"))


def test_preview_with_from_observations_is_rejected(tmp_path: Path) -> None:
    obs = write_observations(tmp_path / "obs.jsonl", scenario()[:10])
    cam = write_camera_yaml(tmp_path / "cam.yaml")
    args = ["replay", "--from-observations", str(obs), "--camera-config", str(cam)]
    result = CliRunner().invoke(app, [*args, "--out", str(tmp_path / "o"), "--preview"])
    assert result.exit_code != 0
    assert "--preview" in result.output


def test_draw_debug_overlay_draws_on_copy() -> None:
    obs = scenario()[0]
    image = np.zeros((180, 320, 3), dtype=np.uint8)
    state = BodyStateSnapshot(
        body_state=BodyState.LYING,
        observation_quality=ObservationQuality.GOOD,
        activity_level=ActivityLevel.UNKNOWN,
        rest_status=RestStatus.UNKNOWN,
        face_status=FaceStatus.NOT_VISIBLE,
        face_signals=FaceSignals(),
    )
    event = EngineEvent(
        code=EventCode.SIT_UP,
        priority=Priority.INFO,
        occurred_at_ms=0,
        detected_at_ms=0,
        confidence=1.0,
        observation_quality=ObservationQuality.GOOD,
        explanation={"rule_id": "test"},
    )
    drawn = draw_debug_overlay(image, obs, BED_ROI, state, [event])
    assert drawn.shape == image.shape
    assert not image.any()
    assert drawn.any()
