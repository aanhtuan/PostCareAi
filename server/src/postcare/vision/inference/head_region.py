"""Ước lượng vùng đầu từ keypoint đầu của pose (F25 R3, R4; A05).

Dùng chung cho nhánh face (ảnh cắt chạy Face Landmarker) và làm mờ khuôn mặt khi hiển thị (F28),
để chỉ có một cách tính vùng đầu. Module này không import mediapipe/cv2.

Cách tính: lấy các keypoint đầu (`nose`, mắt, tai) có visibility ≥ ngưỡng, bounding box của chúng,
cạnh lớn hơn × `scale`, làm vuông quanh tâm bbox. Cần ít nhất hai keypoint để có kích thước.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from postcare.schemas.observation import KeypointName, PersonPose

HEAD_KEYPOINTS = (
    KeypointName.NOSE,
    KeypointName.LEFT_EYE,
    KeypointName.RIGHT_EYE,
    KeypointName.LEFT_EAR,
    KeypointName.RIGHT_EAR,
)
MIN_HEAD_KEYPOINTS = 2
"""Một điểm không cho biết kích thước đầu (giả định F25)."""


@dataclass(frozen=True)
class HeadBox:
    """Vùng đầu hình vuông theo pixel của khung gốc: tâm (cx, cy), cạnh `side`."""

    cx: float
    cy: float
    side: float

    @property
    def side_px(self) -> int:
        """`head_box_px` của `FaceObservation` (cạnh làm tròn, chưa kẹp vào khung)."""
        return round(self.side)

    def bounds(self, image_size: tuple[int, int]) -> tuple[int, int, int, int]:
        """(x0, y0, x1, y1) nguyên, kẹp vào khung `image_size = (width, height)`; có thể rỗng."""
        width, height = image_size
        x0 = round(self.cx - self.side / 2)
        y0 = round(self.cy - self.side / 2)
        x1, y1 = x0 + self.side_px, y0 + self.side_px
        return (
            min(max(x0, 0), width),
            min(max(y0, 0), height),
            min(max(x1, 0), width),
            min(max(y1, 0), height),
        )


def estimate_head_box(
    person: PersonPose,
    image_size: tuple[int, int],
    *,
    min_visibility: float,
    scale: float,
) -> HeadBox | None:
    """Vùng đầu của `person`, hoặc `None` khi không đủ keypoint đầu nhìn rõ.

    `min_visibility`: `pose.min_keypoint_visibility`. `scale`: `face.head_crop_scale` (F25) hoặc
    `privacy.head_box_scale` (F28).
    """
    width, height = image_size
    points = [
        (kp.x * width, kp.y * height)
        for name in HEAD_KEYPOINTS
        if (kp := person.keypoints.get(name)) is not None and kp.visibility >= min_visibility
    ]
    if len(points) < MIN_HEAD_KEYPOINTS:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    extent = max(max(xs) - min(xs), max(ys) - min(ys))
    if extent <= 0:
        return None
    return HeadBox(
        cx=(min(xs) + max(xs)) / 2,
        cy=(min(ys) + max(ys)) / 2,
        side=extent * scale,
    )


def crop_head(image: np.ndarray, box: HeadBox) -> np.ndarray:
    """Ảnh cắt vùng đầu (bản sao liên tục trong bộ nhớ). Vùng nằm ngoài khung → mảng rỗng."""
    height, width = image.shape[:2]
    x0, y0, x1, y1 = box.bounds((width, height))
    return np.ascontiguousarray(image[y0:y1, x0:x1])
