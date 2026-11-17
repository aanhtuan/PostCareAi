"""F11 AC2 (R3, R4, R7): `MediaPipePoseAdapter` với landmarker giả, không cần file model thật."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.observation import FrameObservation, KeypointName
from postcare.settings import REPO_ROOT
from postcare.vision.camera import Frame
from postcare.vision.inference.base import ModelNotFoundError, PoseAdapter
from postcare.vision.inference.pose_mediapipe import MediaPipePoseAdapter


class FakeLandmarker:
    """Thay `mediapipe...PoseLandmarker`: ghi lại input, trả kết quả dựng sẵn."""

    def __init__(self, n_persons: int = 1) -> None:
        self.n_persons = n_persons
        self.calls: list[tuple[Any, int]] = []
        self.closed = False

    def detect_for_video(self, image: Any, timestamp_ms: int) -> Any:
        self.calls.append((image, timestamp_ms))
        pose = [SimpleNamespace(x=0.5, y=1.2, visibility=0.8) for _ in range(33)]
        return SimpleNamespace(pose_landmarks=[pose] * self.n_persons)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def model_file(tmp_path: Path) -> Path:
    path = tmp_path / "pose_landmarker_full.task"
    path.write_bytes(b"fake")
    return path


def _adapter(model_file: Path, fake: FakeLandmarker, num_poses: int = 2) -> MediaPipePoseAdapter:
    created: list[tuple[Path, int]] = []

    def factory(path: Path, n: int) -> FakeLandmarker:
        created.append((path, n))
        return fake

    adapter = MediaPipePoseAdapter(model_file, num_poses=num_poses, landmarker_factory=factory)
    assert created == [(model_file, num_poses)]
    return adapter


def _frame(index: int, ts_ms: int) -> Frame:
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    image[..., 0] = 255  # BGR: kênh xanh dương
    return Frame(image=image, ts_ms=ts_ms, frame_index=index)


def test_adapter_maps_result_to_frame_observation(model_file: Path) -> None:
    fake = FakeLandmarker(n_persons=2)
    adapter: PoseAdapter = _adapter(model_file, fake)
    obs = adapter.observe(_frame(3, 100), camera_id=5)
    assert isinstance(obs, FrameObservation)
    assert (obs.camera_id, obs.frame_index, obs.ts_ms) == (5, 3, 100)
    assert obs.image_size == (64, 48)
    assert obs.source_ok is True
    assert obs.face is None
    assert len(obs.persons) == 2
    nose = obs.persons[0].keypoints[KeypointName.NOSE]
    assert (nose.x, nose.y, nose.visibility) == (0.5, 1.0, 0.8)  # y = 1.2 bị kẹp


def test_adapter_passes_rgb_and_frame_timestamp(model_file: Path) -> None:
    fake = FakeLandmarker()
    adapter = _adapter(model_file, fake)
    adapter.observe(_frame(0, 40), camera_id=1)
    adapter.observe(_frame(1, 73), camera_id=1)
    assert [ts for _, ts in fake.calls] == [40, 73]
    rgb = np.asarray(fake.calls[0][0].numpy_view())
    assert rgb.shape == (48, 64, 3)
    assert rgb[0, 0].tolist() == [0, 0, 255]  # BGR (255, 0, 0) → RGB (0, 0, 255)


def test_adapter_empty_result_gives_no_persons(model_file: Path) -> None:
    adapter = _adapter(model_file, FakeLandmarker(n_persons=0))
    obs = adapter.observe(_frame(0, 0), camera_id=1)
    assert obs.persons == []
    assert obs.source_ok is True


def test_adapter_rejects_non_increasing_ts_unit(model_file: Path) -> None:
    fake = FakeLandmarker()
    adapter = _adapter(model_file, fake)
    adapter.observe(_frame(0, 100), camera_id=1)
    with pytest.raises(ValueError, match="ts_ms"):
        adapter.observe(_frame(1, 100), camera_id=1)
    with pytest.raises(ValueError, match="ts_ms"):
        adapter.observe(_frame(2, 50), camera_id=1)
    assert len(fake.calls) == 1  # model không bị gọi với timestamp sai


def test_adapter_num_poses_from_engine_config(model_file: Path) -> None:
    config = EngineConfig.load(REPO_ROOT / "config" / "engine.default.yaml")
    seen: list[int] = []

    def factory(path: Path, n: int) -> FakeLandmarker:
        seen.append(n)
        return FakeLandmarker()

    MediaPipePoseAdapter.from_config(model_file, config, landmarker_factory=factory)
    assert seen == [config.pose.num_poses] == [2]


def test_adapter_close_closes_landmarker(model_file: Path) -> None:
    fake = FakeLandmarker()
    adapter = _adapter(model_file, fake)
    adapter.close()
    assert fake.closed
    adapter.close()  # gọi lại không lỗi


def test_adapter_missing_model_suggests_make_models(tmp_path: Path) -> None:
    with pytest.raises(ModelNotFoundError, match="make models"):
        MediaPipePoseAdapter(tmp_path / "khong-co.task", num_poses=2)


def test_adapter_unreadable_model_suggests_make_models(model_file: Path) -> None:
    def broken(path: Path, n: int) -> FakeLandmarker:
        raise RuntimeError("Unable to open file")

    with pytest.raises(ModelNotFoundError, match="make models"):
        MediaPipePoseAdapter(model_file, num_poses=2, landmarker_factory=broken)


def test_real_mediapipe_rejects_corrupt_model_file(model_file: Path) -> None:
    """Không cần model thật: file .task hỏng → lỗi gợi ý `make models` (R7)."""
    with pytest.raises(ModelNotFoundError, match="make models"):
        MediaPipePoseAdapter(model_file, num_poses=2)
