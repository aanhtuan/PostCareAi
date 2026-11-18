"""F25 R3, R4: ước lượng vùng đầu từ keypoint đầu của pose (dùng chung với F28)."""

from __future__ import annotations

import numpy as np
import pytest

from postcare.schemas.observation import Keypoint, KeypointName, PersonPose
from postcare.vision.inference.head_region import HeadBox, crop_head, estimate_head_box

K = KeypointName
SIZE = (1000, 500)


def _person(points: dict[KeypointName, tuple[float, float, float]]) -> PersonPose:
    w, h = SIZE
    return PersonPose(
        keypoints={n: Keypoint(x=x / w, y=y / h, visibility=v) for n, (x, y, v) in points.items()}
    )


def test_head_box_is_scaled_square_around_head_keypoints() -> None:
    person = _person(
        {
            K.NOSE: (500, 250, 0.9),
            K.LEFT_EAR: (540, 240, 0.9),
            K.RIGHT_EAR: (460, 240, 0.9),
            K.LEFT_EYE: (515, 235, 0.9),
            K.LEFT_SHOULDER: (700, 400, 0.9),  # không phải keypoint đầu: bỏ qua
        }
    )
    box = estimate_head_box(person, SIZE, min_visibility=0.5, scale=1.5)
    assert box is not None
    # bbox 80 × 15 → cạnh lớn 80 × 1.5 = 120, tâm (500, 242.5)
    assert box.side == pytest.approx(120)
    assert (box.cx, box.cy) == pytest.approx((500, 242.5))
    assert box.side_px == 120
    assert box.bounds(SIZE) == (440, 182, 560, 302)


def test_low_visibility_head_keypoints_are_ignored() -> None:
    person = _person(
        {
            K.NOSE: (500, 250, 0.9),
            K.LEFT_EAR: (540, 240, 0.2),
            K.RIGHT_EAR: (460, 240, 0.2),
            K.LEFT_EYE: (520, 240, 0.9),
        }
    )
    box = estimate_head_box(person, SIZE, min_visibility=0.5, scale=1.0)
    assert box is not None
    assert box.side == pytest.approx(20)


def test_single_visible_head_keypoint_gives_no_box() -> None:
    person = _person({K.NOSE: (500, 250, 0.9), K.LEFT_EAR: (540, 240, 0.1)})
    assert estimate_head_box(person, SIZE, min_visibility=0.5, scale=1.6) is None


def test_no_head_keypoints_gives_no_box() -> None:
    assert estimate_head_box(PersonPose(keypoints={}), SIZE, min_visibility=0.5, scale=1.6) is None


def test_crop_head_clips_to_image() -> None:
    image = np.arange(500 * 1000 * 3, dtype=np.uint32).reshape(500, 1000, 3).astype(np.uint8)
    inside = crop_head(image, HeadBox(cx=500, cy=250, side=100))
    assert inside.shape == (100, 100, 3)
    assert inside.flags["C_CONTIGUOUS"]
    edge = crop_head(image, HeadBox(cx=10, cy=10, side=100))
    assert edge.shape == (60, 60, 3)
    outside = crop_head(image, HeadBox(cx=-500, cy=-500, side=100))
    assert outside.size == 0
