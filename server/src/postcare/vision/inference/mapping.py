"""Ánh xạ 33 landmark của MediaPipe Pose → `KeypointName` trung lập (F11 R4, R6; PDF §10).

Bảng chỉ số chỉ nằm ở đây. Hàm nhận dữ liệu thuần (x, y, visibility) theo chỉ số MediaPipe,
nên test chạy được không cần model và không import mediapipe.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from postcare.schemas.observation import Keypoint, KeypointName, PersonPose

MEDIAPIPE_LANDMARK_COUNT = 33
"""Số landmark của MediaPipe Pose Landmarker (lite / full / heavy đều 33)."""

# Chỉ số theo tài liệu "Pose landmark detection guide" của MediaPipe. Các điểm còn lại
# (mắt trong/ngoài, miệng, ngón út/trỏ/cái của bàn tay) không có trong KeypointName (F10 R3).
MEDIAPIPE_POSE_INDEX: Mapping[KeypointName, int] = {
    KeypointName.NOSE: 0,
    KeypointName.LEFT_EYE: 2,
    KeypointName.RIGHT_EYE: 5,
    KeypointName.LEFT_EAR: 7,
    KeypointName.RIGHT_EAR: 8,
    KeypointName.LEFT_SHOULDER: 11,
    KeypointName.RIGHT_SHOULDER: 12,
    KeypointName.LEFT_ELBOW: 13,
    KeypointName.RIGHT_ELBOW: 14,
    KeypointName.LEFT_WRIST: 15,
    KeypointName.RIGHT_WRIST: 16,
    KeypointName.LEFT_HIP: 23,
    KeypointName.RIGHT_HIP: 24,
    KeypointName.LEFT_KNEE: 25,
    KeypointName.RIGHT_KNEE: 26,
    KeypointName.LEFT_ANKLE: 27,
    KeypointName.RIGHT_ANKLE: 28,
    KeypointName.LEFT_HEEL: 29,
    KeypointName.RIGHT_HEEL: 30,
    KeypointName.LEFT_FOOT_INDEX: 31,
    KeypointName.RIGHT_FOOT_INDEX: 32,
}

RawLandmark = tuple[float, float, float | None]
"""(x, y, visibility) chuẩn hóa theo khung hình; visibility `None` nếu model không trả."""


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def landmarks_to_person(landmarks: Sequence[RawLandmark]) -> PersonPose:
    """Chuyển 33 landmark của một người thành `PersonPose`.

    x, y, visibility được kẹp vào [0, 1] (model có thể trả toạ độ ngoài khung; giả định của spec).
    Visibility giữ giá trị model (F13 dùng để đánh giá chất lượng); thiếu → 0.
    Sai số landmark hoặc giá trị không hữu hạn → `ValueError`.
    """
    if len(landmarks) != MEDIAPIPE_LANDMARK_COUNT:
        raise ValueError(
            f"MediaPipe Pose phải trả {MEDIAPIPE_LANDMARK_COUNT} landmark, nhận {len(landmarks)}"
        )
    keypoints: dict[KeypointName, Keypoint] = {}
    for name, idx in MEDIAPIPE_POSE_INDEX.items():
        x, y, vis = landmarks[idx]
        visibility = 0.0 if vis is None else vis
        if not all(math.isfinite(v) for v in (x, y, visibility)):
            raise ValueError(f"Landmark {idx} ({name.value}) có giá trị không hữu hạn: {x}, {y}")
        keypoints[name] = Keypoint(x=_clamp(x), y=_clamp(y), visibility=_clamp(visibility))
    return PersonPose(keypoints=keypoints)
