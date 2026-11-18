"""F25 AC3, R1, R6, R8: `MediaPipeFaceAdapter` với landmarker giả (không cần model thật)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from postcare.vision.inference.base import ModelNotFoundError
from postcare.vision.inference.face_landmarker import (
    MediaPipeFaceAdapter,
    blendshape_keys_from_config,
    open_face_adapter,
)
from tests.face.helpers import config_keys, face_config


class FakeFaceLandmarker:
    """Thay `FaceLandmarker`: trả mọi tên trong `names` (giống model trả đủ 52 blendshape)."""

    def __init__(self, names: list[str], *, found: bool = True) -> None:
        self.names = names
        self.found = found
        self.calls: list[tuple[Any, int]] = []
        self.closed = False

    def detect_for_video(self, image: Any, timestamp_ms: int) -> Any:
        self.calls.append((image, timestamp_ms))
        if not self.found:
            return SimpleNamespace(face_landmarks=[], face_blendshapes=[])
        cats = [
            SimpleNamespace(category_name=n, score=(i + 1) / (len(self.names) + 1))
            for i, n in enumerate(self.names)
        ]
        return SimpleNamespace(face_landmarks=[[object()]], face_blendshapes=[cats])

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def model_file(tmp_path: Path) -> Path:
    path = tmp_path / "face_landmarker.task"
    path.write_bytes(b"fake")
    return path


def _adapter(model_file: Path, fake: FakeFaceLandmarker, keys: set[str]) -> MediaPipeFaceAdapter:
    return MediaPipeFaceAdapter(model_file, keys, landmarker_factory=lambda _p: fake)


def _crop() -> np.ndarray:
    return np.zeros((40, 40, 3), dtype=np.uint8)


def test_adapter_filters_keys_from_config(model_file: Path) -> None:
    config = face_config()
    keys = blendshape_keys_from_config(config)
    assert keys == config_keys(config)
    model_names = [*sorted(keys), "someOtherBlendshape", "_neutral"]
    fake = FakeFaceLandmarker(model_names)
    out = _adapter(model_file, fake, keys).detect(_crop(), 10)
    assert out is not None
    assert set(out) == keys

    # Đổi danh sách khóa trong config (không sửa code) → output đổi theo.
    signals = config.face.signals.model_dump()
    signals["eyes_closed"]["keys"] = ["someOtherBlendshape"]
    changed = face_config(signals=signals)
    new_keys = blendshape_keys_from_config(changed)
    assert "someOtherBlendshape" in new_keys
    out2 = _adapter(model_file, FakeFaceLandmarker(model_names), new_keys).detect(_crop(), 10)
    assert out2 is not None
    assert set(out2) == new_keys
    assert "_neutral" not in out2


def test_adapter_no_face_returns_none(model_file: Path) -> None:
    fake = FakeFaceLandmarker(["a"], found=False)
    assert _adapter(model_file, fake, {"a"}).detect(_crop(), 5) is None


def test_adapter_uses_video_timestamps_and_rgb(model_file: Path) -> None:
    fake = FakeFaceLandmarker(["a"])
    adapter = _adapter(model_file, fake, {"a"})
    crop = _crop()
    crop[..., 0] = 255  # BGR: xanh dương
    adapter.detect(crop, 40)
    adapter.detect(crop, 90)
    assert [ts for _, ts in fake.calls] == [40, 90]
    rgb = np.asarray(fake.calls[0][0].numpy_view())
    assert rgb.shape == (40, 40, 3)
    assert tuple(rgb[0, 0]) == (0, 0, 255)
    with pytest.raises(ValueError, match="tăng ngặt"):
        adapter.detect(crop, 90)
    adapter.close()
    assert fake.closed


def test_adapter_missing_model_raises(tmp_path: Path) -> None:
    with pytest.raises(ModelNotFoundError, match="make models"):
        MediaPipeFaceAdapter(tmp_path / "nope.task", {"a"})


def test_open_face_adapter_missing_model_returns_none(tmp_path: Path) -> None:
    """R8: thiếu model face không làm dừng pipeline, chỉ ghi WARNING."""
    assert open_face_adapter(tmp_path / "nope.task", face_config()) is None
