"""F25 AC1, AC2 (R2, R3, R5, R7, R8): cổng chất lượng khuôn mặt với bộ phát hiện giả."""

from __future__ import annotations

import logging

import pytest
from postcare.vision.inference.face_gate import FaceGate

from postcare.schemas.enums import FaceStatus
from tests.face.helpers import (
    FakeFaceDetector,
    config_keys,
    face_config,
    head_person,
    image_frame,
)

SCALE = 1.6


def _half_width_for(head_box_px: float, scale: float = SCALE) -> float:
    """Nửa bề rộng tai–tai để `head_box_px = 2 × half × scale`."""
    return head_box_px / (2 * scale)


def _gate(detector: FakeFaceDetector | None, **face: object) -> FaceGate:
    config = face_config(**{"head_crop_scale": SCALE, "run_every_n_frames": 1, **face})
    return FaceGate.from_config(config, detector)


def test_face_gate_calls_landmarker_only_when_head_large_enough() -> None:
    detector = FakeFaceDetector({"x": 0.1})
    gate = _gate(detector, min_head_box_px=80)

    small = gate.observe(image_frame(0, 0), head_person(_half_width_for(79)))
    assert small is not None
    assert small.status == FaceStatus.TOO_SMALL
    assert small.head_box_px == 79
    assert detector.calls == []

    nobody = gate.observe(image_frame(1, 100), None)
    assert nobody is not None
    assert nobody.status == FaceStatus.NOT_VISIBLE
    assert detector.calls == []

    ok = gate.observe(image_frame(2, 200), head_person(_half_width_for(160)))
    assert ok is not None
    assert ok.head_box_px == 160
    # Chạy trên ảnh cắt vùng đầu (vuông, cạnh = head_box_px), không phải cả khung 1280×720.
    assert detector.calls == [((160, 160, 3), 200)]


def test_face_gate_threshold_is_inclusive() -> None:
    detector = FakeFaceDetector({"x": 0.1})
    gate = _gate(detector, min_head_box_px=80)
    obs = gate.observe(image_frame(0, 0), head_person(_half_width_for(80)))
    assert obs is not None
    assert obs.head_box_px == 80
    assert len(detector.calls) == 1


def test_face_runs_every_n_frames() -> None:
    detector = FakeFaceDetector({"x": 0.1})
    gate = _gate(detector, run_every_n_frames=3)
    person = head_person(_half_width_for(160))
    results = [gate.observe(image_frame(i, i * 66), person) for i in range(7)]
    ran = [r is not None for r in results]
    assert ran == [True, False, False, True, False, False, True]
    assert [ts for _, ts in detector.calls] == [0, 198, 396]


def test_face_not_run_frames_count_even_without_target() -> None:
    """Chu kỳ N frame tính theo khung đã xử lý, kể cả khung không có người."""
    detector = FakeFaceDetector({"x": 0.1})
    gate = _gate(detector, run_every_n_frames=2)
    assert gate.observe(image_frame(0, 0), None) is not None
    assert gate.observe(image_frame(1, 66), head_person(80)) is None
    assert gate.observe(image_frame(2, 132), head_person(80)) is not None


def test_face_status_classification() -> None:
    keys = config_keys(face_config())
    some_key = sorted(keys)[0]
    detector = FakeFaceDetector({some_key: 0.7})
    gate = _gate(detector, min_head_box_px=80)
    big = _half_width_for(160)

    # LOW_CONFIDENCE: keypoint đầu visibility thấp → không ước lượng được vùng đầu.
    low = gate.observe(image_frame(0, 0), head_person(big, visibility=0.1))
    assert low is not None
    assert (low.status, low.head_box_px) == (FaceStatus.LOW_CONFIDENCE, 0)
    assert detector.calls == []

    # TOO_SMALL
    small = gate.observe(image_frame(1, 100), head_person(_half_width_for(40)))
    assert small is not None
    assert small.status == FaceStatus.TOO_SMALL
    assert detector.calls == []

    # NOT_VISIBLE: không có người mục tiêu
    none = gate.observe(image_frame(2, 200), None)
    assert none is not None
    assert (none.status, none.head_box_px, none.blendshapes) == (FaceStatus.NOT_VISIBLE, 0, {})

    # OK: thấy mặt, có blendshape
    ok = gate.observe(image_frame(3, 300), head_person(big))
    assert ok is not None
    assert ok.status == FaceStatus.OK
    assert ok.blendshapes == {some_key: 0.7}

    # NOT_VISIBLE: landmarker không tìm thấy mặt trong ảnh cắt
    detector.scores = None
    gone = gate.observe(image_frame(4, 400), head_person(big))
    assert gone is not None
    assert gone.status == FaceStatus.NOT_VISIBLE
    assert gone.head_box_px == 160
    assert gate.error_count == 0


def test_face_adapter_error_is_not_visible_and_counted(caplog: pytest.LogCaptureFixture) -> None:
    detector = FakeFaceDetector(error=RuntimeError("model hỏng"))
    gate = _gate(detector)
    with caplog.at_level(logging.WARNING):
        results = [
            gate.observe(image_frame(i, i * 100), head_person(_half_width_for(160)))
            for i in range(3)
        ]
    assert all(r is not None and r.status == FaceStatus.NOT_VISIBLE for r in results)
    assert gate.error_count == 3
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_face_missing_detector_is_not_visible() -> None:
    """Model face thiếu → không có detector: vẫn trả NOT_VISIBLE, đếm lỗi, không raise (R8)."""
    gate = _gate(None)
    obs = gate.observe(image_frame(0, 0), head_person(_half_width_for(160)))
    assert obs is not None
    assert obs.status == FaceStatus.NOT_VISIBLE
    assert gate.error_count == 1


def test_face_crop_outside_frame_is_clipped() -> None:
    """Vùng đầu tràn mép khung: ảnh cắt bị kẹp vào khung, head_box_px vẫn là cạnh gốc."""
    from tests.engine.builders import LYING
    from tests.face.helpers import with_head

    detector = FakeFaceDetector({"x": 0.1})
    gate = _gate(detector)
    person = with_head(LYING.person(), half_width_px=_half_width_for(160), center_px=(10, 10))
    obs = gate.observe(image_frame(0, 0), person)
    assert obs is not None
    assert obs.head_box_px == 160
    (h, w, _), _ts = detector.calls[0]
    assert 0 < w < 160
    assert 0 < h < 160


def test_gate_filters_unknown_blendshape_keys() -> None:
    config = face_config()
    keys = sorted(config_keys(config))
    detector = FakeFaceDetector({keys[0]: 0.2, "notAConfiguredKey": 0.9})
    gate = FaceGate.from_config(face_config(run_every_n_frames=1, head_crop_scale=SCALE), detector)
    obs = gate.observe(image_frame(0, 0), head_person(_half_width_for(160)))
    assert obs is not None
    assert obs.blendshapes == {keys[0]: 0.2}
