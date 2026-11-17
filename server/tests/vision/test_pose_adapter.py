"""F11 AC2, AC3: `MediaPipePoseAdapter` với model thật (marker `vision`, `make test-vision`).

Cần model trong `models/` (`make models`) và một video có người:
- `data/vision/*.mp4|*.avi` (giả định thư mục của spec), nếu không có thì
- clip stock `data/external/pexels/pexels-8090735.mp4` (datasets.md; một người rời giường).

Thư mục gốc đổi được bằng `POSTCARE_DATA_DIR`, `POSTCARE_MODELS_DIR` (ví dụ khi chạy trong
git worktree không có `data/`). Thiếu model hoặc video → skip. Không ghi khung hình ra đĩa.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from postcare.vision.inference.pose_mediapipe import MediaPipePoseAdapter
from postcare.vision.models import load_manifest

from postcare.schemas import observation as schema_observation
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.observation import FrameObservation, KeypointName
from postcare.settings import REPO_ROOT
from postcare.vision.camera import FileSource, Frame

pytestmark = pytest.mark.vision

DATA_DIR = Path(os.environ.get("POSTCARE_DATA_DIR", REPO_ROOT / "data"))
MODELS_DIR = Path(os.environ.get("POSTCARE_MODELS_DIR", REPO_ROOT / "models"))
FALLBACK_CLIP = DATA_DIR / "external" / "pexels" / "pexels-8090735.mp4"


def _clip() -> Path:
    own = sorted(p for p in (DATA_DIR / "vision").glob("*") if p.suffix.lower() in {".mp4", ".avi"})
    if own:
        return own[0]
    if FALLBACK_CLIP.is_file():
        return FALLBACK_CLIP
    pytest.skip(f"Không có video trong {DATA_DIR / 'vision'} hoặc {FALLBACK_CLIP}")


def _model_path() -> Path:
    manifest = load_manifest(REPO_ROOT / "config" / "models.yaml")
    path = MODELS_DIR / manifest.pose_entry().filename
    if not path.is_file():
        pytest.skip(f"Thiếu model {path}: chạy `make models`")
    return path


@pytest.fixture
def adapter() -> Iterator[MediaPipePoseAdapter]:
    config = EngineConfig.load(REPO_ROOT / "config" / "engine.default.yaml")
    ad = MediaPipePoseAdapter.from_config(_model_path(), config)
    yield ad
    ad.close()


def _frames(path: Path, n: int) -> list[Frame]:
    frames: list[Frame] = []
    with FileSource(path, max_fps=10) as src:
        while len(frames) < n:
            frame = src.read()
            if frame is None:
                break
            frames.append(frame)
    return frames


def test_adapter_detects_person_in_clip(adapter: MediaPipePoseAdapter) -> None:
    frames = _frames(_clip(), 30)
    assert frames, "không đọc được khung nào"
    obs = [adapter.observe(f, camera_id=1) for f in frames]
    with_person = [o for o in obs if o.persons]
    assert len(with_person) >= len(obs) // 2, f"{len(with_person)}/{len(obs)} khung có người"
    assert all(len(o.persons) <= 2 for o in obs)  # num_poses = 2 (A04)
    person = with_person[-1].persons[0]
    assert KeypointName.LEFT_SHOULDER in person.keypoints
    assert len(person.keypoints) == len(KeypointName)


def test_adapter_empty_frame_gives_no_persons(adapter: MediaPipePoseAdapter) -> None:
    black = np.zeros((720, 1280, 3), dtype=np.uint8)
    obs = adapter.observe(Frame(image=black, ts_ms=0, frame_index=0), camera_id=1)
    assert obs.persons == []
    assert obs.source_ok is True
    assert obs.image_size == (1280, 720)


def test_adapter_returns_schema_types_only(adapter: MediaPipePoseAdapter) -> None:
    frames = _frames(_clip(), 10)
    for f in frames:
        obs = adapter.observe(f, camera_id=1)
        assert type(obs) is FrameObservation
        for person in obs.persons:
            assert type(person) is schema_observation.PersonPose
            for name, kp in person.keypoints.items():
                assert type(name) is KeypointName
                assert type(kp) is schema_observation.Keypoint
                assert 0.0 <= kp.x <= 1.0 and 0.0 <= kp.y <= 1.0
        # Không còn đối tượng nào của mediapipe trong dữ liệu đã dump.
        assert "mediapipe" not in repr(obs.model_dump())


def test_adapter_rejects_non_increasing_ts(adapter: MediaPipePoseAdapter) -> None:
    black = np.zeros((480, 640, 3), dtype=np.uint8)
    adapter.observe(Frame(image=black, ts_ms=100, frame_index=0), camera_id=1)
    with pytest.raises(ValueError, match="ts_ms"):
        adapter.observe(Frame(image=black, ts_ms=100, frame_index=1), camera_id=1)
