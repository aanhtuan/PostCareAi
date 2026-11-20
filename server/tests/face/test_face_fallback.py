"""Nhánh face khi engine chưa có người mục tiêu (camera không theo dõi giường, cận cảnh webcam).

Cận cảnh: hông nằm ngoài khung, MediaPipe kẹp toạ độ về y = 1.0 (mép dưới) nên engine không
chọn được mục tiêu từ ROI toàn khung. Hồ sơ không gắn giường vẫn phải đọc được mặt người rõ nhất;
hồ sơ theo dõi giường thì không (không đọc mặt người ngoài vùng giường).
"""

from __future__ import annotations

from postcare.engine import Engine
from postcare.pipeline import process_frame
from postcare.schemas.context import EngineContext
from postcare.schemas.enums import FaceStatus
from postcare.schemas.observation import FrameObservation, Keypoint, PersonPose
from postcare.schemas.roi import RoiPolygon, validate_roi_polygon
from postcare.vision.camera import Frame
from postcare.vision.inference.face_gate import FaceGate
from tests.engine.builders import BED_ROI, IMAGE_SIZE, LYING
from tests.face.helpers import (
    FakeFaceDetector,
    K,
    face_config,
    image_frame,
    observation_of,
    with_head,
)

FULL_FRAME = validate_roi_polygon([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])


class _Adapter:
    def __init__(self, persons: list[PersonPose]) -> None:
        self.persons = persons

    def observe(self, frame: Frame, camera_id: int) -> FrameObservation:
        return observation_of(frame, self.persons)

    def close(self) -> None:
        pass


def _close_up(cx: float, half_width_px: float) -> PersonPose:
    """Người ngồi sát webcam: đầu rõ, hai hông bị kẹp ở mép dưới khung."""
    kps = dict(LYING.person().keypoints)
    for name in (K.LEFT_HIP, K.RIGHT_HIP):
        kps[name] = Keypoint(x=kps[name].x, y=1.0, visibility=0.1)
    return with_head(
        PersonPose(keypoints=kps), half_width_px=half_width_px, center_px=(cx, IMAGE_SIZE[1] * 0.35)
    )


def _run(
    persons: list[PersonPose], *, roi: RoiPolygon = FULL_FRAME, face_fallback: bool
) -> tuple[FaceStatus, FakeFaceDetector]:
    config = face_config(run_every_n_frames=1)
    detector = FakeFaceDetector({"eyeBlinkLeft": 0.1, "eyeBlinkRight": 0.1})
    gate = FaceGate.from_config(config, detector)
    engine = Engine(config, EngineContext(camera_id=1, roi_polygon=roi))
    obs, out = process_frame(
        image_frame(0, 1), _Adapter(persons), engine, gate, face_fallback=face_fallback
    )
    assert obs.face is not None
    return out.state.face_status, detector


def test_close_up_without_target_reads_face_when_fallback_enabled() -> None:
    status, detector = _run([_close_up(640, 120)], face_fallback=True)
    assert status == FaceStatus.OK
    assert len(detector.calls) == 1


def test_close_up_without_fallback_stays_not_visible() -> None:
    """Ca âm tính: theo dõi giường không đọc mặt người chưa là mục tiêu."""
    status, detector = _run([_close_up(640, 120)], roi=BED_ROI, face_fallback=False)
    assert status == FaceStatus.NOT_VISIBLE
    assert detector.calls == []


def test_fallback_picks_person_with_largest_head() -> None:
    big, small = _close_up(900, 140), _close_up(300, 50)
    _, detector = _run([small, big], face_fallback=True)
    ((shape, _),) = detector.calls
    # Vùng đầu 2 × 140 × head_crop_scale (2.2) ≈ 616 px, không phải 220 px của người nhỏ.
    assert shape[0] > 400


def test_fallback_without_person_stays_not_visible() -> None:
    status, detector = _run([], face_fallback=True)
    assert status == FaceStatus.NOT_VISIBLE
    assert detector.calls == []
