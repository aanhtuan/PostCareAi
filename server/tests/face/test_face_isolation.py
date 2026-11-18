"""F25 AC2 (R7, R8, R9; HS §4.1): lỗi nhánh face không đổi trạng thái/sự kiện cơ thể."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from postcare.engine import Engine
from postcare.pipeline import process_frame
from postcare.replay.camera_config import load_camera_config
from postcare.replay.runner import replay_video
from postcare.schemas.enums import FaceStatus
from postcare.schemas.observation import FrameObservation
from postcare.vision.inference.face_gate import FaceGate
from tests.engine.builders import IMAGE_SIZE, PoseSequence
from tests.face.helpers import FakeFaceDetector, face_config, with_head
from tests.replay.helpers import fake_source_and_adapter, write_camera_yaml

HEAD_HALF_WIDTH = 60.0  # vùng đầu 2 × 60 × face.head_crop_scale (2.2) = 264 px ≥ 80 px


def _scenario() -> list[FrameObservation]:
    """Nằm → ngồi → mép giường → đứng → ra ngoài (có sự kiện cơ thể), có keypoint đầu."""
    seq = (
        PoseSequence(fps=15)
        .lying(seconds=3)
        .raise_to_sitting(seconds=1)
        .sitting(seconds=3)
        .move_to_edge(seconds=1)
        .standing(seconds=3)
        .walk_out(seconds=2)
        .drop_landmarks(seconds=2, mode="missing")
        .lying(seconds=2)
        .build()
    )
    return [
        o.model_copy(
            update={"persons": [with_head(p, half_width_px=HEAD_HALF_WIDTH) for p in o.persons]}
        )
        for o in seq
    ]


def _replay(tmp_path: Path, name: str, gate: FaceGate | None) -> Path:
    camera = load_camera_config(write_camera_yaml(tmp_path / "cam.yaml"))
    config = face_config(enabled=gate is not None)
    source, adapter = fake_source_and_adapter(_scenario(), size=IMAGE_SIZE)
    out = tmp_path / name
    replay_video(source, adapter, camera, config, out, face=gate)
    return out


def _events(out: Path) -> list[dict[str, Any]]:
    rows = [json.loads(x) for x in (out / "events.jsonl").read_text("utf-8").splitlines()]
    for r in rows:
        r.pop("config_hash")  # face.enabled nằm trong config_hash
    return rows


def _frames(out: Path) -> list[str]:
    return (out / "frames.jsonl").read_text("utf-8").splitlines()


def test_face_error_does_not_stop_body(tmp_path: Path) -> None:
    detector = FakeFaceDetector(error=RuntimeError("face hỏng"))
    gate = FaceGate.from_config(face_config(), detector)
    broken = _replay(tmp_path, "face-error", gate)
    disabled = _replay(tmp_path, "face-off", None)

    assert detector.calls, "landmarker giả phải được gọi (vùng đầu đủ lớn)"
    assert gate.error_count == len(detector.calls)
    body_events = _events(disabled)
    assert body_events, "kịch bản phải có sự kiện cơ thể"
    assert _events(broken) == body_events
    assert _frames(broken) == _frames(disabled)

    observations = [
        FrameObservation.model_validate_json(x)
        for x in (broken / "observations.jsonl").read_text("utf-8").splitlines()
    ]
    faces = [o.face for o in observations]
    assert faces[1] is None  # run_every_n_frames = 2: frame lẻ không chạy face
    assert {f.status for f in faces if f is not None} >= {FaceStatus.NOT_VISIBLE}
    assert all(f is None for f in json_faces(disabled))


def json_faces(out: Path) -> list[object]:
    return [
        json.loads(x)["face"] for x in (out / "observations.jsonl").read_text("utf-8").splitlines()
    ]


def test_process_frame_attaches_face_observation(tmp_path: Path) -> None:
    camera = load_camera_config(write_camera_yaml(tmp_path / "cam.yaml"))
    config = face_config(run_every_n_frames=1)
    observations = _scenario()[:3]
    source, adapter = fake_source_and_adapter(observations, size=IMAGE_SIZE)
    detector = FakeFaceDetector({})
    gate = FaceGate.from_config(config, detector)
    engine = Engine(config, camera.context())
    with source:
        frame = source.read()
    assert frame is not None
    obs, _ = process_frame(frame, adapter, engine, face=gate)
    assert obs.face is not None
    assert obs.face.status == FaceStatus.OK
    assert obs.face.head_box_px == round(2 * HEAD_HALF_WIDTH * config.face.head_crop_scale)
    plain, _ = process_frame(frame, adapter, Engine(config, camera.context()))
    assert plain.face is None
