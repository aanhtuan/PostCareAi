"""Render khung hình: chế độ hiển thị riêng tư (F28) và lớp debug của replay (F12 R6).

- Chế độ hiển thị (F28 R4–R7; PDF §11): worker render khung theo `display_mode` **trước** khi nén
  JPEG và gửi lên API, nên API/MJPEG chỉ chuyển tiếp ảnh đã render.
  - `RAW`: bản sao ảnh gốc (chỉ dùng trong môi trường thử nghiệm).
  - `BLUR` (mặc định, A08): pixelate vùng đầu của mọi người pose phát hiện. Vùng đầu lấy từ
    keypoint pose (`head_region`, dùng chung với F25), không phụ thuộc Face Landmarker. Không ước
    lượng được vùng đầu → giữ vùng gần nhất tối đa `privacy.head_hold_s`, quá thì mờ toàn khung.
  - `SKELETON`: vẽ trên nền trơn mới tạo, chỉ có Bed ROI và skeleton; hàm chỉ nhận kích thước
    khung nên không thể chép pixel gốc.
- `draw_debug_overlay`: skeleton, ROI, `body_state` + `observation_quality`, nhãn sự kiện vừa
  phát cho `postcare replay --preview`. Nhãn dùng mã nội bộ (công cụ dev, không phải UI).

Không sửa ảnh gốc, không ghi ảnh ra đĩa (QA#29; `preview.mp4` do replay ghi khi được yêu cầu).
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.enums import DisplayMode
from postcare.schemas.events import EngineEvent
from postcare.schemas.observation import FrameObservation, KeypointName, PersonPose
from postcare.schemas.roi import RoiPolygon
from postcare.schemas.state import BodyStateSnapshot
from postcare.vision.camera import Image
from postcare.vision.inference.head_region import HeadBox, estimate_head_box

K = KeypointName
SKELETON: tuple[tuple[KeypointName, KeypointName], ...] = (
    (K.LEFT_SHOULDER, K.RIGHT_SHOULDER),
    (K.LEFT_HIP, K.RIGHT_HIP),
    (K.LEFT_SHOULDER, K.LEFT_HIP),
    (K.RIGHT_SHOULDER, K.RIGHT_HIP),
    (K.LEFT_SHOULDER, K.LEFT_ELBOW),
    (K.LEFT_ELBOW, K.LEFT_WRIST),
    (K.RIGHT_SHOULDER, K.RIGHT_ELBOW),
    (K.RIGHT_ELBOW, K.RIGHT_WRIST),
    (K.LEFT_HIP, K.LEFT_KNEE),
    (K.LEFT_KNEE, K.LEFT_ANKLE),
    (K.RIGHT_HIP, K.RIGHT_KNEE),
    (K.RIGHT_KNEE, K.RIGHT_ANKLE),
    (K.LEFT_ANKLE, K.LEFT_HEEL),
    (K.LEFT_HEEL, K.LEFT_FOOT_INDEX),
    (K.RIGHT_ANKLE, K.RIGHT_HEEL),
    (K.RIGHT_HEEL, K.RIGHT_FOOT_INDEX),
    (K.NOSE, K.LEFT_EYE),
    (K.NOSE, K.RIGHT_EYE),
    (K.LEFT_EYE, K.LEFT_EAR),
    (K.RIGHT_EYE, K.RIGHT_EAR),
)
DRAW_MIN_VISIBILITY = 0.5
"""Keypoint dưới mức này vẽ mờ (chỉ để nhìn; không phải ngưỡng engine)."""

# Màu BGR.
_ROI = (0, 220, 255)
_BONE = (0, 255, 0)
_BONE_DIM = (0, 110, 0)
_JOINT = (255, 255, 255)
_TEXT = (255, 255, 255)
_EVENT = (0, 0, 255)
_PANEL = (0, 0, 0)
_SKELETON_BACKGROUND = (24, 24, 24)
"""Nền trơn của chế độ SKELETON (chỉ để nhìn)."""

DEFAULT_DISPLAY_MODE = DisplayMode.BLUR
"""A08; cũng là chế độ dự phòng khi giá trị thiếu hoặc không hợp lệ (F28 R1)."""


def resolve_display_mode(value: object) -> DisplayMode:
    """Chế độ hiển thị từ cấu hình; thiếu hoặc không hợp lệ → `BLUR` (F28 R1)."""
    if isinstance(value, DisplayMode):
        return value
    if isinstance(value, str):
        try:
            return DisplayMode(value)
        except ValueError:
            pass
    return DEFAULT_DISPLAY_MODE


def pixelate(region: Image, blocks: int) -> Image:
    """Pixelate `region` thành tối đa `blocks` khối theo cạnh dài (trả ảnh mới)."""
    h, w = region.shape[:2]
    if h == 0 or w == 0:
        return region.copy()
    longest = max(h, w)
    bw = max(1, min(w, round(blocks * w / longest)))
    bh = max(1, min(h, round(blocks * h / longest)))
    small = cv2.resize(region, (bw, bh), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


def render_raw(image: Image) -> Image:
    """`RAW`: bản sao ảnh gốc."""
    return image.copy()


def render_blur(image: Image, boxes: Sequence[HeadBox] | None, blocks: int) -> Image:
    """`BLUR`: pixelate từng vùng đầu; `boxes=None` → pixelate toàn khung (F28 R6, R7)."""
    if boxes is None:
        return pixelate(image, blocks)
    out = image.copy()
    h, w = out.shape[:2]
    for box in boxes:
        x0, y0, x1, y1 = box.bounds((w, h))
        if x1 > x0 and y1 > y0:
            out[y0:y1, x0:x1] = pixelate(out[y0:y1, x0:x1], blocks)
    return out


def render_skeleton(
    shape: tuple[int, ...], persons: Sequence[PersonPose], roi: RoiPolygon | None
) -> Image:
    """`SKELETON`: nền trơn mới + Bed ROI + skeleton. Chỉ nhận kích thước khung (F28 R5)."""
    h, w = int(shape[0]), int(shape[1])
    out = np.empty((h, w, 3), dtype=np.uint8)
    out[:, :] = _SKELETON_BACKGROUND
    thick = _thickness(h)
    if roi is not None:
        _draw_roi(out, roi, thick)
    for person in persons:
        _draw_person(out, person, w, h, thick)
    return out


class PrivacyRenderer:
    """Chọn hàm render theo chế độ; giữ vùng đầu gần nhất cho `BLUR` (F28 R7).

    Thời gian tính bằng `ts_ms` của khung (không đọc đồng hồ). `ts_ms` lùi (nguồn mở lại) → vùng
    đầu đã nhớ coi như hết hạn.
    """

    def __init__(
        self,
        *,
        head_box_scale: float,
        pixelate_blocks: int,
        head_hold_s: float,
        min_visibility: float,
    ) -> None:
        self.head_box_scale = head_box_scale
        self.pixelate_blocks = pixelate_blocks
        self.head_hold_ms = head_hold_s * 1000.0
        self.min_visibility = min_visibility
        self._last_boxes: list[HeadBox] = []
        self._last_ts_ms: int | None = None

    @classmethod
    def from_config(cls, config: EngineConfig) -> PrivacyRenderer:
        """Khóa `privacy.*` và `pose.min_keypoint_visibility` của cấu hình engine."""
        return cls(
            head_box_scale=config.privacy.head_box_scale,
            pixelate_blocks=config.privacy.pixelate_blocks,
            head_hold_s=config.privacy.head_hold_s,
            min_visibility=config.pose.min_keypoint_visibility,
        )

    def reset(self) -> None:
        """Quên vùng đầu đã nhớ (ví dụ khi mở lại nguồn)."""
        self._last_boxes = []
        self._last_ts_ms = None

    def render(
        self,
        image: Image,
        persons: Sequence[PersonPose],
        *,
        ts_ms: int,
        mode: DisplayMode,
        roi: RoiPolygon | None,
    ) -> Image:
        """Khung đã render theo `mode` (ảnh mới; không sửa `image`)."""
        if mode is DisplayMode.RAW:
            return render_raw(image)
        if mode is DisplayMode.SKELETON:
            return render_skeleton(image.shape, persons, roi)
        h, w = image.shape[:2]
        return render_blur(image, self._head_boxes(persons, (w, h), ts_ms), self.pixelate_blocks)

    def _head_boxes(
        self, persons: Sequence[PersonPose], size: tuple[int, int], ts_ms: int
    ) -> list[HeadBox] | None:
        """Vùng đầu cần làm mờ, hoặc `None` = mờ toàn khung."""
        estimated = [
            estimate_head_box(
                p, size, min_visibility=self.min_visibility, scale=self.head_box_scale
            )
            for p in persons
        ]
        found = [b for b in estimated if b is not None]
        if persons and len(found) == len(persons):
            self._last_boxes = found
            self._last_ts_ms = ts_ms
            return found
        # Không có người, hoặc có người không ước lượng được vùng đầu (R7).
        last = self._last_ts_ms
        if last is not None and 0 <= ts_ms - last <= self.head_hold_ms:
            return [*found, *self._last_boxes]
        return None


def _thickness(height: int) -> int:
    return max(1, round(2 * max(height / 720.0, 0.25)))


def _draw_roi(out: Image, roi: RoiPolygon, thick: int) -> None:
    h, w = out.shape[:2]
    pts = np.array([[round(x * w), round(y * h)] for x, y in roi.points], dtype=np.int32)
    cv2.polylines(out, [pts], isClosed=True, color=_ROI, thickness=thick)


def draw_debug_overlay(
    image: Image,
    obs: FrameObservation,
    roi: RoiPolygon,
    state: BodyStateSnapshot,
    events: Sequence[EngineEvent] = (),
) -> Image:
    """Trả bản sao của `image` (BGR) đã vẽ lớp debug."""
    out = image.copy()
    h, w = out.shape[:2]
    scale = max(h / 720.0, 0.25)
    thick = _thickness(h)
    _draw_roi(out, roi, thick)
    for person in obs.persons:
        _draw_person(out, person, w, h, thick)
    lines = [
        (f"{state.body_state.value} | {state.observation_quality.value}", _TEXT),
        (f"t={obs.ts_ms / 1000:.2f}s #{obs.frame_index} persons={len(obs.persons)}", _TEXT),
        *[(f"{e.code.value} ({e.priority.value})", _EVENT) for e in events],
    ]
    font_scale = 0.6 * scale
    line_h = max(8, round(26 * scale))
    panel_w = min(w, round(520 * scale))
    cv2.rectangle(out, (0, 0), (panel_w, line_h * len(lines) + line_h // 3), _PANEL, -1)
    for i, (text, color) in enumerate(lines):
        org = (round(6 * scale), line_h * (i + 1) - line_h // 4)
        cv2.putText(out, text, org, cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thick, cv2.LINE_AA)
    return out


def _draw_person(out: Image, person: PersonPose, w: int, h: int, thick: int) -> None:
    kps = person.keypoints

    def px(name: KeypointName) -> tuple[int, int]:
        kp = kps[name]
        return round(kp.x * (w - 1)), round(kp.y * (h - 1))

    for a, b in SKELETON:
        if a in kps and b in kps:
            visible = min(kps[a].visibility, kps[b].visibility) >= DRAW_MIN_VISIBILITY
            cv2.line(out, px(a), px(b), _BONE if visible else _BONE_DIM, thick, cv2.LINE_AA)
    for name, kp in kps.items():
        if kp.visibility >= DRAW_MIN_VISIBILITY:
            cv2.circle(out, px(name), thick + 1, _JOINT, -1, cv2.LINE_AA)


def encode_jpeg(image: Image, *, max_side: int = 960, quality: int = 70) -> bytes:
    """Nén khung thành JPEG cho xem trực tiếp (F06 R7; A03).

    Ảnh vào đã render theo chế độ hiển thị (`PrivacyRenderer`, F28). Thu nhỏ để cạnh dài
    ≤ `max_side` (không phóng to). Chỉ trả bytes trong RAM, không ghi đĩa (QA#29).
    """
    h, w = image.shape[:2]
    longest = max(h, w)
    if max_side > 0 and longest > max_side:
        scale = max_side / longest
        size = (max(1, round(w * scale)), max(1, round(h * scale)))
        image = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    if not ok:
        raise ValueError("OpenCV không nén được khung JPEG")
    return bytes(buf.tobytes())
