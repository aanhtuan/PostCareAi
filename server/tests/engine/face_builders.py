"""Builder quan sát khuôn mặt tổng hợp cho test F26 (testing.md mục 2). Không có ảnh, không model.

Một kịch bản mặt là danh sách đoạn `face(signals={…}, seconds=…)`, gắn lần lượt theo `ts_ms` vào
các `FrameObservation` sinh từ `PoseSequence`. Giá trị của một tín hiệu được gán cho **mọi** khóa
blendshape của tín hiệu đó (lấy từ `face.signals.*.keys` trong config), các khóa khác bằng 0.

```python
frames = with_face(
    PoseSequence(fps=15).lying(seconds=20).build(),
    [face(seconds=3), face(signals={"brow_down": 0.9, "eye_squint": 0.9}, seconds=10)],
)
```
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.enums import FaceStatus
from postcare.schemas.observation import FaceObservation, FrameObservation
from tests.engine.builders import default_config

HEAD_PX = 160
"""Cạnh vùng đầu tổng hợp (px), lớn hơn `face.min_head_box_px`."""

ON = 0.95
"""Giá trị blendshape rõ ràng trên mọi ngưỡng mặc định."""
OFF = 0.05


@dataclass(frozen=True)
class FaceSegment:
    seconds: float
    signals: Mapping[str, float] = field(default_factory=dict)
    status: FaceStatus = FaceStatus.OK
    blendshapes: Mapping[str, float] | None = None
    """Ghi đè trực tiếp bộ blendshape (khi cần chỉ một khóa của tín hiệu)."""
    missing: bool = False
    """True → các frame của đoạn có `face = None` (frame không chạy face)."""


def face(
    signals: Mapping[str, float] | None = None,
    seconds: float = 1.0,
    status: FaceStatus = FaceStatus.OK,
    blendshapes: Mapping[str, float] | None = None,
    missing: bool = False,
) -> FaceSegment:
    return FaceSegment(seconds, dict(signals or {}), status, blendshapes, missing)


def all_keys(config: EngineConfig) -> dict[str, list[str]]:
    sig = config.face.signals
    return {name: list(getattr(sig, name).keys) for name in type(sig).model_fields}


def face_obs(segment: FaceSegment, config: EngineConfig) -> FaceObservation | None:
    if segment.missing:
        return None
    if segment.status != FaceStatus.OK:
        return FaceObservation(status=segment.status, head_box_px=HEAD_PX, blendshapes={})
    if segment.blendshapes is not None:
        shapes = dict(segment.blendshapes)
    else:
        shapes = {}
        for name, keys in all_keys(config).items():
            value = segment.signals.get(name, 0.0)
            for key in keys:
                shapes[key] = value
    return FaceObservation(status=FaceStatus.OK, head_box_px=HEAD_PX, blendshapes=shapes)


def with_face(
    frames: Sequence[FrameObservation],
    segments: Sequence[FaceSegment],
    config: EngineConfig | None = None,
    every_n: int = 1,
) -> list[FrameObservation]:
    """Gắn mặt theo đoạn (tính từ `ts_ms` của frame đầu). Hết kịch bản → `face = None`.

    `every_n` > 1: chỉ frame có `frame_index % every_n == 0` mang mặt (giống `run_every_n_frames`).
    """
    cfg = config or default_config()
    out: list[FrameObservation] = []
    if not frames:
        return out
    t0 = frames[0].ts_ms
    bounds: list[tuple[float, FaceSegment]] = []
    end = 0.0
    for seg in segments:
        end += seg.seconds * 1000
        bounds.append((end, seg))
    for obs in frames:
        rel = obs.ts_ms - t0
        current = next((s for b, s in bounds if rel < b), None)
        if current is None or obs.frame_index % every_n != 0:
            out.append(obs)
            continue
        out.append(obs.model_copy(update={"face": face_obs(current, cfg)}))
    return out
