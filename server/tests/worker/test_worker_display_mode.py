"""F28 AC1 (phía worker), R1, R3, R4: worker render khung theo `display_mode` trước khi gửi."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from postcare.schemas.enums import DisplayMode, ObservationProfile
from postcare.settings import REPO_ROOT
from postcare.worker.config import WorkerConfig
from postcare.worker.loop import default_engine_factory
from tests.worker.helpers import default_config, make_harness

SOURCE_GRAY = 80  # FakeFrameSource: khung xám 80


def _decode(jpeg: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    return image


def _frames(h: Any, since: float = 0.0) -> list[np.ndarray]:
    return [_decode(c[3]) for c in h.api.paths("/frame") if c[0] >= since]


def test_worker_applies_new_display_mode() -> None:
    h = make_harness(config=default_config(display_mode="RAW"))
    h.run_until(3.0)
    raw = _frames(h)
    assert raw and all(abs(float(np.median(f)) - SOURCE_GRAY) < 5 for f in raw)
    changed_at = h.time.t
    h.api.config.update(display_mode="SKELETON", config_version=2)
    assert h.worker.config is not None
    for _ in range(100_000):
        if h.worker.config.display_mode is DisplayMode.SKELETON:
            break
        h.worker.step()
    applied_at = h.time.t
    assert applied_at - changed_at <= 5.0
    h.run_until(applied_at - 100.0 + 2.0)
    skeleton = _frames(h, since=applied_at)
    assert skeleton
    # Nền trơn mới: không còn màu xám của nguồn ở phần lớn khung.
    for f in skeleton:
        assert float(np.median(f)) < SOURCE_GRAY / 2
    # Đổi chế độ hiển thị không tạo lại engine (R8).
    assert len(h.engines) == 1


def test_skeleton_frames_do_not_depend_on_source_pixels() -> None:
    a = make_harness(config=default_config(display_mode="SKELETON"))
    a.run_until(2.0)
    jpeg_a = [c[3] for c in a.api.paths("/frame")]
    # Nguồn giả mã hóa số khung ở pixel (0, 0): khung RAW khác nhau, khung SKELETON thì không.
    assert len(jpeg_a) >= 5
    assert len(set(jpeg_a)) == 1


def test_worker_invalid_or_missing_display_mode_uses_blur() -> None:
    cfg = default_config(display_mode="FOO")
    assert WorkerConfig.model_validate(cfg).display_mode is DisplayMode.BLUR
    missing = default_config()
    del missing["display_mode"]
    assert WorkerConfig.model_validate(missing).display_mode is DisplayMode.BLUR
    assert WorkerConfig.model_validate(default_config(display_mode=None)).display_mode is (
        DisplayMode.BLUR
    )
    h = make_harness(config=cfg)
    h.run_until(2.0)
    assert h.worker.config is not None and h.worker.config.display_mode is DisplayMode.BLUR
    assert h.api.paths("/frame")  # vẫn gửi khung, không dừng worker


class _BrokenRenderer:
    """Render luôn lỗi (review F28): worker bỏ khung, không bao giờ gửi ảnh gốc."""

    def __init__(self) -> None:
        self.calls = 0

    def render(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        raise RuntimeError("render lỗi")

    def reset(self) -> None:
        pass


def test_render_error_drops_frame_and_keeps_running() -> None:
    h = make_harness(config=default_config(display_mode="BLUR"))
    broken = _BrokenRenderer()
    h.worker.renderer = broken  # type: ignore[assignment]
    h.run_until(5.0)
    assert broken.calls > 0
    assert h.api.paths("/frame") == []  # không gửi khung nào, kể cả ảnh gốc
    assert h.engines and len(h.engines[0].processed) > 10  # engine vẫn chạy
    assert h.api.paths("/state")  # trạng thái vẫn gửi
    assert h.api.paths("/heartbeat")


def test_worker_sends_separate_skeleton_without_changing_display_mode() -> None:
    h = make_harness(config=default_config(display_mode="RAW"))
    h.run_until(2.0)
    primary = h.api.paths("/frame")
    skeleton = h.api.paths("/frame?view=skeleton")
    assert primary and len(skeleton) == len(primary)
    assert all(float(np.median(_decode(c[3]))) < SOURCE_GRAY / 2 for c in skeleton)
    assert all(abs(float(np.median(_decode(c[3]))) - SOURCE_GRAY) < 5 for c in primary)
    assert h.worker.config.display_mode is DisplayMode.RAW


def test_no_roi_observes_pose_for_display_without_engine_or_events() -> None:
    h = make_harness(config=default_config(roi_polygon=None, display_mode="BLUR"))
    h.run_until(2.0)
    assert h.adapters[0].calls
    assert not h.engines
    assert not h.api.paths("/state")
    assert not h.api.paths("/events")
    assert h.api.paths("/frame?view=skeleton")


def test_non_bed_profile_ignores_saved_bed_roi() -> None:
    cfg = WorkerConfig.model_validate(
        default_config(
            observation_profile=ObservationProfile.ABNORMAL_MOVEMENT,
            roi_polygon=[[0.2, 0.2], [0.8, 0.2], [0.8, 0.9], [0.2, 0.9]],
        )
    )
    engine = default_engine_factory(REPO_ROOT / "config" / "engine.default.yaml")(cfg)
    assert engine.context.roi_polygon.points == [
        (0.0, 0.0),
        (1.0, 0.0),
        (1.0, 1.0),
        (0.0, 1.0),
    ]
