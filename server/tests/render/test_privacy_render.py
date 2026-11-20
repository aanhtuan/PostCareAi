"""F28 AC2, AC3, R1, R5–R7: render RAW / BLUR / SKELETON trong worker (khung tổng hợp)."""

from __future__ import annotations

import numpy as np
import pytest

from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.enums import DisplayMode
from postcare.schemas.observation import KeypointName, PersonPose
from postcare.vision.inference.head_region import estimate_head_box
from postcare.vision.render import (
    PrivacyRenderer,
    encode_jpeg,
    render_skeleton,
    resolve_display_mode,
)
from tests.engine.builders import BED_ROI, person_from_px
from tests.replay.helpers import DEFAULT_ENGINE

K = KeypointName
W, H = 320, 240
SIZE = (W, H)
MARK = (13, 201, 77)  # BGR; màu đánh dấu của nguồn
MARK2 = (240, 17, 133)


def _config() -> EngineConfig:
    return EngineConfig.load(DEFAULT_ENGINE)


def _renderer() -> PrivacyRenderer:
    return PrivacyRenderer.from_config(_config())


def _hold_ms() -> int:
    return round(_config().privacy.head_hold_s * 1000)


def _noise(seed: int) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, 256, (H, W, 3), dtype=np.uint8)


def _marked() -> np.ndarray:
    """Ảnh nguồn chỉ gồm hai màu đánh dấu xen kẽ (dễ nhận nếu bị chép sang output)."""
    image = np.zeros((H, W, 3), dtype=np.uint8)
    image[:, :] = MARK
    image[::2, ::2] = MARK2
    return image


def _body(dx: float = 0.0, *, head: bool = True, ears_only: bool = False) -> PersonPose:
    pts = {
        K.LEFT_SHOULDER: (120 + dx, 120),
        K.RIGHT_SHOULDER: (160 + dx, 120),
        K.LEFT_HIP: (125 + dx, 190),
        K.RIGHT_HIP: (155 + dx, 190),
        K.LEFT_ELBOW: (110 + dx, 155),
        K.RIGHT_ELBOW: (170 + dx, 155),
    }
    if head and ears_only:
        # Mặt quay đi: chỉ thấy hai tai (không mắt, không mũi); Face Landmarker không thấy mặt.
        pts.update({K.LEFT_EAR: (130 + dx, 90), K.RIGHT_EAR: (150 + dx, 90)})
    elif head:
        pts.update(
            {
                K.NOSE: (140 + dx, 92),
                K.LEFT_EYE: (135 + dx, 88),
                K.RIGHT_EYE: (145 + dx, 88),
                K.LEFT_EAR: (128 + dx, 90),
                K.RIGHT_EAR: (152 + dx, 90),
            }
        )
    return person_from_px(pts, image_size=SIZE)


def _head_bounds(person: PersonPose) -> tuple[int, int, int, int]:
    cfg = _config()
    box = estimate_head_box(
        person,
        SIZE,
        min_visibility=cfg.pose.min_keypoint_visibility,
        scale=cfg.privacy.head_box_scale,
    )
    assert box is not None
    return box.bounds(SIZE)


def _outside(bounds: list[tuple[int, int, int, int]]) -> np.ndarray:
    mask = np.ones((H, W), dtype=bool)
    for x0, y0, x1, y1 in bounds:
        mask[y0:y1, x0:x1] = False
    return mask


def _has_color(image: np.ndarray, color: tuple[int, int, int]) -> bool:
    return bool(np.all(image == np.array(color, dtype=np.uint8), axis=-1).any())


def _assert_fully_blurred(image: np.ndarray, out: np.ndarray) -> None:
    assert out.shape == image.shape
    # Toàn khung đã pixelate: còn rất ít màu, mọi ô 8×8 đều khác ảnh gốc.
    assert len(np.unique(out.reshape(-1, 3), axis=0)) < 500
    for y in range(0, H, 40):
        for x in range(0, W, 40):
            assert not np.array_equal(image[y : y + 8, x : x + 8], out[y : y + 8, x : x + 8])


# ---------- R1: chế độ dự phòng ----------


@pytest.mark.parametrize("value", [None, "", "FOO", "blur ", 3, "skeleton"])
def test_invalid_display_mode_defaults_to_blur(value: object) -> None:
    assert resolve_display_mode(value) is DisplayMode.BLUR


@pytest.mark.parametrize("mode", list(DisplayMode))
def test_valid_display_mode_is_kept(mode: DisplayMode) -> None:
    assert resolve_display_mode(mode) is mode
    assert resolve_display_mode(mode.value) is mode


# ---------- RAW ----------


def test_raw_render_is_copy() -> None:
    image = _noise(1)
    out = _renderer().render(image, [_body()], ts_ms=0, mode=DisplayMode.RAW, roi=BED_ROI)
    assert np.array_equal(out, image)
    assert out is not image


# ---------- AC2 / R5: SKELETON không chứa pixel gốc ----------


def test_skeleton_render_independent_of_source_pixels() -> None:
    persons = [_body(), _body(dx=100)]
    outs = [
        _renderer().render(src, persons, ts_ms=0, mode=DisplayMode.SKELETON, roi=BED_ROI)
        for src in (_noise(1), _noise(2), _marked())
    ]
    assert outs[0].shape == (H, W, 3)
    assert outs[0].tobytes() == outs[1].tobytes() == outs[2].tobytes()
    assert outs[0].any()  # có skeleton + ROI, không phải khung trống
    assert not _has_color(outs[2], MARK)
    assert not _has_color(outs[2], MARK2)
    # JPEG gửi đi cũng giống từng byte.
    assert encode_jpeg(outs[0]) == encode_jpeg(outs[2])


def test_skeleton_only_needs_frame_shape() -> None:
    out = render_skeleton((H, W), [_body()], BED_ROI)
    assert out.shape == (H, W, 3) and out.dtype == np.uint8
    assert out.any()
    empty = render_skeleton((H, W), [], None)
    assert len(np.unique(empty.reshape(-1, 3), axis=0)) == 1  # chỉ nền trơn


# ---------- AC3 / R6, R7: BLUR vùng đầu từ pose ----------


def test_blur_uses_pose_head_region_without_face() -> None:
    image = _noise(3)
    person = _body(ears_only=True)
    out = _renderer().render(image, [person], ts_ms=0, mode=DisplayMode.BLUR, roi=BED_ROI)
    x0, y0, x1, y1 = _head_bounds(person)
    assert x1 > x0 and y1 > y0
    head_out = out[y0:y1, x0:x1]
    assert not np.array_equal(image[y0:y1, x0:x1], head_out)
    # Pixelate: vùng đầu chỉ còn ≤ blocks² màu (ảnh nhiễu gốc gần như mỗi pixel một màu).
    blocks = _config().privacy.pixelate_blocks
    assert len(np.unique(head_out.reshape(-1, 3), axis=0)) <= blocks**2
    mask = _outside([(x0, y0, x1, y1)])
    assert np.array_equal(out[mask], image[mask])


def test_blur_two_people() -> None:
    image = _noise(4)
    a, b = _body(), _body(dx=120)
    out = _renderer().render(image, [a, b], ts_ms=0, mode=DisplayMode.BLUR, roi=BED_ROI)
    bounds = [_head_bounds(a), _head_bounds(b)]
    for x0, y0, x1, y1 in bounds:
        assert not np.array_equal(image[y0:y1, x0:x1], out[y0:y1, x0:x1])
    mask = _outside(bounds)
    assert np.array_equal(out[mask], image[mask])


def test_blur_holds_last_head_box_within_hold() -> None:
    renderer = _renderer()
    person = _body()
    renderer.render(_noise(5), [person], ts_ms=0, mode=DisplayMode.BLUR, roi=BED_ROI)
    image = _noise(6)
    # Người còn đó nhưng không thấy đầu (hoặc pose mất người): dùng vùng đầu đã nhớ.
    for persons in ([_body(head=False)], []):
        out = renderer.render(image, persons, ts_ms=_hold_ms(), mode=DisplayMode.BLUR, roi=None)
        x0, y0, x1, y1 = _head_bounds(person)
        assert not np.array_equal(image[y0:y1, x0:x1], out[y0:y1, x0:x1])
        mask = _outside([(x0, y0, x1, y1)])
        assert np.array_equal(out[mask], image[mask])


def test_blur_keeps_frame_when_no_person() -> None:
    renderer = _renderer()
    renderer.render(_noise(7), [_body()], ts_ms=0, mode=DisplayMode.BLUR, roi=BED_ROI)
    image = _noise(8)
    out = renderer.render(image, [], ts_ms=_hold_ms() + 1, mode=DisplayMode.BLUR, roi=BED_ROI)
    assert np.array_equal(out, image)


def test_blur_without_any_head_ever_keeps_frame() -> None:
    image = _noise(9)
    out = _renderer().render(image, [], ts_ms=0, mode=DisplayMode.BLUR, roi=None)
    assert np.array_equal(out, image)


def test_blur_partial_head_detection_only_blurs_found_head() -> None:
    """Hai người, chỉ vùng đầu ước lượng được mới bị làm mờ."""
    image = _noise(10)
    persons = [_body(), _body(dx=120, head=False)]
    out = _renderer().render(image, persons, ts_ms=0, mode=DisplayMode.BLUR, roi=None)
    x0, y0, x1, y1 = _head_bounds(persons[0])
    assert not np.array_equal(image[y0:y1, x0:x1], out[y0:y1, x0:x1])
    assert np.array_equal(out[_outside([(x0, y0, x1, y1)])], image[_outside([(x0, y0, x1, y1)])])


def test_blur_timestamp_going_back_expires_hold() -> None:
    renderer = _renderer()
    renderer.render(_noise(11), [_body()], ts_ms=10_000, mode=DisplayMode.BLUR, roi=None)
    image = _noise(12)
    out = renderer.render(image, [], ts_ms=0, mode=DisplayMode.BLUR, roi=None)
    assert np.array_equal(out, image)


def test_blur_does_not_modify_input() -> None:
    image = _noise(13)
    before = image.copy()
    _renderer().render(image, [_body()], ts_ms=0, mode=DisplayMode.BLUR, roi=None)
    _renderer().render(image, [], ts_ms=0, mode=DisplayMode.SKELETON, roi=BED_ROI)
    assert np.array_equal(image, before)
