"""Tiện ích test F12: cấu hình camera, nguồn giả, adapter giả. Không có media, không model."""

from collections.abc import Sequence
from pathlib import Path

import yaml

from postcare.schemas.observation import FrameObservation, PersonPose
from postcare.settings import REPO_ROOT
from postcare.vision.fake import FakeFrameSource
from postcare.vision.inference.fake import FakePoseAdapter
from tests.engine.builders import BED_ROI, CAMERA_ID, PoseSequence

FPS = 15
DEFAULT_ENGINE = REPO_ROOT / "config" / "engine.default.yaml"


def write_camera_yaml(path: Path, **override: object) -> Path:
    data: dict[str, object] = {
        "version": 1,
        "camera_id": CAMERA_ID,
        "roi_polygon": [list(p) for p in BED_ROI.points],
        "thresholds": {},
    }
    data.update(override)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def scenario() -> list[FrameObservation]:
    """Nằm → ngồi → mất người → nằm lại (chỉ toạ độ, builder F13)."""
    return (
        PoseSequence(fps=FPS)
        .lying(seconds=3)
        .raise_to_sitting(seconds=1)
        .sitting(seconds=3)
        .drop_landmarks(seconds=3, mode="missing")
        .lying(seconds=2)
        .build()
    )


def fake_source_and_adapter(
    observations: Sequence[FrameObservation],
    size: tuple[int, int] = (64, 48),
) -> tuple[FakeFrameSource, FakePoseAdapter]:
    persons: dict[int, Sequence[PersonPose]] = {o.frame_index: o.persons for o in observations}
    source = FakeFrameSource([o.ts_ms for o in observations], size=size)
    return source, FakePoseAdapter(persons)


def write_observations(path: Path, observations: Sequence[FrameObservation]) -> Path:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for obs in observations:
            f.write(obs.model_dump_json() + "\n")
    return path
