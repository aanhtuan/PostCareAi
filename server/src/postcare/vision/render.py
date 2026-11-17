"""Vẽ lớp debug lên khung hình cho `postcare replay --preview` (F12 R6; công cụ dev).

Vẽ skeleton của mọi người, polygon ROI, `body_state` + `observation_quality` hiện tại và nhãn
sự kiện vừa phát. Nhãn dùng mã nội bộ (công cụ dev, không phải UI người dùng cuối; giả định của
spec). Không sửa ảnh gốc, không ghi ảnh ra đĩa (việc ghi `preview.mp4` do replay làm khi được yêu
cầu).
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

from postcare.schemas.events import EngineEvent
from postcare.schemas.observation import FrameObservation, KeypointName, PersonPose
from postcare.schemas.roi import RoiPolygon
from postcare.schemas.state import BodyStateSnapshot
from postcare.vision.camera import Image

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
    thick = max(1, round(2 * scale))
    pts = np.array([[round(x * w), round(y * h)] for x, y in roi.points], dtype=np.int32)
    cv2.polylines(out, [pts], isClosed=True, color=_ROI, thickness=thick)
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
    """Nén khung RAW thành JPEG cho xem trực tiếp (F06 R7; A03).

    Thu nhỏ để cạnh dài ≤ `max_side` (không phóng to). Chỉ trả bytes trong RAM, không ghi đĩa
    (QA#29). Chế độ BLUR / SKELETON do F28 thêm.
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
