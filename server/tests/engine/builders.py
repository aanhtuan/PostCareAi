"""Builder chuỗi pose tổng hợp cho test engine (testing.md mục 2; F13 R10). Không có ảnh.

Mô hình thân đơn giản theo pixel: tâm hông + các vector lệch tới tâm vai, gối, cổ chân, cộng nửa bề
rộng vai/hông. Mỗi thao tác (`lying`, `raise_to_sitting`…) sinh các `FrameObservation` cách đều
theo `fps`; thời gian chỉ là `ts_ms` tính từ chỉ số frame, không dùng đồng hồ thật.

```python
seq = PoseSequence(fps=15).lying(seconds=3).raise_to_sitting(seconds=1.5).build()
```
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from postcare.engine import Engine
from postcare.schemas.context import EngineContext
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.events import EngineOutput
from postcare.schemas.observation import FrameObservation, Keypoint, KeypointName, PersonPose
from postcare.schemas.roi import RoiPolygon

ROOT = Path(__file__).resolve().parents[3]
IMAGE_SIZE = (1280, 720)
BED_ROI = RoiPolygon(points=[(0.2, 0.3), (0.8, 0.3), (0.8, 0.8), (0.2, 0.8)])
"""Giường nằm ngang trong khung 16:9: x 256–1024 px, y 216–576 px. Trục dài nằm ngang."""
CAMERA_ID = 1
VISIBLE = 0.95
LOW_VISIBILITY = 0.1

Px = tuple[float, float]

K = KeypointName


def default_config() -> EngineConfig:
    return EngineConfig.load(ROOT / "config" / "engine.default.yaml")


def context(roi: RoiPolygon = BED_ROI) -> EngineContext:
    return EngineContext(camera_id=CAMERA_ID, roi_polygon=roi)


def run_engine(
    seq: Iterable[FrameObservation],
    config: EngineConfig | None = None,
    roi: RoiPolygon = BED_ROI,
) -> list[EngineOutput]:
    engine = Engine(config or default_config(), context(roi))
    return [engine.process(obs) for obs in seq]


def _clamp(v: float) -> float:
    return min(1.0, max(0.0, v))


def person_from_px(
    points: dict[KeypointName, Px],
    image_size: tuple[int, int] = IMAGE_SIZE,
    visibility: float | dict[KeypointName, float] = VISIBLE,
) -> PersonPose:
    """Tạo `PersonPose` từ toạ độ pixel (chuẩn hóa và kẹp về [0, 1])."""
    w, h = image_size
    kps: dict[KeypointName, Keypoint] = {}
    for name, (x, y) in points.items():
        vis = visibility.get(name, VISIBLE) if isinstance(visibility, dict) else visibility
        kps[name] = Keypoint(x=_clamp(x / w), y=_clamp(y / h), visibility=vis)
    return PersonPose(keypoints=kps)


def frame(
    persons: Sequence[PersonPose],
    *,
    ts_ms: int,
    frame_index: int = 0,
    image_size: tuple[int, int] = IMAGE_SIZE,
    source_ok: bool = True,
) -> FrameObservation:
    return FrameObservation(
        camera_id=CAMERA_ID,
        frame_index=frame_index,
        ts_ms=ts_ms,
        image_size=image_size,
        persons=list(persons),
        source_ok=source_ok,
    )


@dataclass(frozen=True)
class Body:
    """Tư thế tổng hợp theo pixel. Vector lệch tính từ tâm hông."""

    hip: Px
    shoulder: Px
    knee: Px
    ankle: Px
    half_width: Px
    """Nửa đường nối hai vai (và hai hông): vai trái = tâm vai + half_width."""

    def moved_to(self, hip: Px) -> "Body":
        return replace(self, hip=hip)

    def points(self) -> dict[KeypointName, Px]:
        hx, hy = self.hip
        sx, sy = hx + self.shoulder[0], hy + self.shoulder[1]
        wx, wy = self.half_width
        kx, ky = hx + self.knee[0], hy + self.knee[1]
        ax, ay = hx + self.ankle[0], hy + self.ankle[1]
        return {
            K.NOSE: (sx + 1.3 * (sx - hx) / 2, sy + 1.3 * (sy - hy) / 2),
            K.LEFT_SHOULDER: (sx + wx, sy + wy),
            K.RIGHT_SHOULDER: (sx - wx, sy - wy),
            K.LEFT_HIP: (hx + wx * 0.7, hy + wy * 0.7),
            K.RIGHT_HIP: (hx - wx * 0.7, hy - wy * 0.7),
            K.LEFT_KNEE: (kx + wx * 0.5, ky + wy * 0.5),
            K.RIGHT_KNEE: (kx - wx * 0.5, ky - wy * 0.5),
            K.LEFT_ANKLE: (ax + wx * 0.5, ay + wy * 0.5),
            K.RIGHT_ANKLE: (ax - wx * 0.5, ay - wy * 0.5),
        }

    def person(
        self, image_size: tuple[int, int] = IMAGE_SIZE, visibility: float = VISIBLE
    ) -> PersonPose:
        return person_from_px(self.points(), image_size, visibility)


def _lerp(a: Px, b: Px, t: float) -> Px:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _lerp_body(a: Body, b: Body, t: float) -> Body:
    return Body(
        hip=_lerp(a.hip, b.hip, t),
        shoulder=_lerp(a.shoulder, b.shoulder, t),
        knee=_lerp(a.knee, b.knee, t),
        ankle=_lerp(a.ankle, b.ankle, t),
        half_width=_lerp(a.half_width, b.half_width, t),
    )


TORSO_PX = 200.0
# Tư thế mẫu theo BED_ROI (x 256–1024, y 216–576), torso 200 px.
LYING = Body(
    hip=(640, 400), shoulder=(-TORSO_PX, 0), knee=(180, 0), ankle=(360, 0), half_width=(0, 35)
)
SITTING = Body(
    hip=(640, 400), shoulder=(0, -TORSO_PX), knee=(180, 0), ankle=(360, 0), half_width=(40, 0)
)
AT_EDGE = Body(
    hip=(640, 550), shoulder=(0, -TORSO_PX), knee=(30, 90), ankle=(30, 160), half_width=(40, 0)
)
STANDING = Body(
    hip=(640, 590), shoulder=(0, -TORSO_PX), knee=(0, 60), ankle=(0, 120), half_width=(40, 0)
)
OUTSIDE = STANDING.moved_to((1180, 590))
"""Đứng ngoài ROI, bên phải giường."""
NURSE = STANDING.moved_to((1150, 400))
"""Điều dưỡng đứng cạnh mép phải giường, tâm hông ngoài ROI."""


class PoseSequence:
    """Chuỗi khung hình tổng hợp. Mọi thao tác trả `self` để viết nối chuỗi."""

    def __init__(
        self,
        fps: float = 15,
        roi: RoiPolygon = BED_ROI,
        image_size: tuple[int, int] = IMAGE_SIZE,
        start: Body = LYING,
    ) -> None:
        self.fps = fps
        self.roi = roi
        self.image_size = image_size
        self.body = start
        self._frames: list[FrameObservation] = []
        self._extras: list[Body] = []

    # ---- tiện ích ----

    @property
    def ts_ms(self) -> int:
        """`ts_ms` của frame kế tiếp."""
        return round(len(self._frames) * 1000 / self.fps)

    def _n(self, seconds: float) -> int:
        return max(1, round(seconds * self.fps))

    def _emit(self, patient: PersonPose | None, *, source_ok: bool = True) -> None:
        persons = [b.person(self.image_size) for b in self._extras]
        if patient is not None:
            persons.append(patient)
        self._frames.append(
            frame(
                persons,
                ts_ms=self.ts_ms,
                frame_index=len(self._frames),
                image_size=self.image_size,
                source_ok=source_ok,
            )
        )

    def _hold(self, body: Body, seconds: float) -> "PoseSequence":
        self.body = body
        for _ in range(self._n(seconds)):
            self._emit(body.person(self.image_size))
        return self

    def _move(self, target: Body, seconds: float) -> "PoseSequence":
        start = self.body
        n = self._n(seconds)
        for i in range(1, n + 1):
            self.body = _lerp_body(start, target, i / n)
            self._emit(self.body.person(self.image_size))
        return self

    # ---- tư thế ----

    def hold(self, seconds: float) -> "PoseSequence":
        return self._hold(self.body, seconds)

    def pose(self, body: Body, seconds: float) -> "PoseSequence":
        return self._hold(body, seconds)

    def lying(self, seconds: float) -> "PoseSequence":
        return self._hold(LYING, seconds)

    def raise_to_sitting(self, seconds: float) -> "PoseSequence":
        return self._move(SITTING, seconds)

    def sitting(self, seconds: float) -> "PoseSequence":
        return self._hold(SITTING, seconds)

    def move_to_edge(self, seconds: float) -> "PoseSequence":
        return self._move(AT_EDGE, seconds)

    def standing(self, seconds: float) -> "PoseSequence":
        return self._hold(STANDING, seconds)

    def walk_out(self, seconds: float, to: Body = OUTSIDE) -> "PoseSequence":
        return self._move(to, seconds)

    def move_to(self, body: Body, seconds: float) -> "PoseSequence":
        return self._move(body, seconds)

    # ---- nhiễu, mất quan sát ----

    def noise(self, frames: int = 2, kind: str = "visibility") -> "PoseSequence":
        """`visibility`: vai/hông tụt visibility. `jump`: toàn bộ keypoint nhảy xa rồi quay về."""
        for _ in range(frames):
            if kind == "visibility":
                self._emit(self.body.person(self.image_size, visibility=LOW_VISIBILITY))
            elif kind == "jump":
                hx, hy = self.body.hip
                jumped = self.body.moved_to((hx - 3 * TORSO_PX, hy - TORSO_PX))
                self._emit(jumped.person(self.image_size))
            else:
                raise ValueError(f"kind lạ: {kind}")
        return self

    def drop_landmarks(self, seconds: float, mode: str = "low_visibility") -> "PoseSequence":
        """`low_visibility`: vẫn có người nhưng visibility thấp (bị che). `missing`: mất người."""
        for _ in range(self._n(seconds)):
            if mode == "low_visibility":
                self._emit(self.body.person(self.image_size, visibility=LOW_VISIBILITY))
            elif mode == "missing":
                self._emit(None)
            else:
                raise ValueError(f"mode lạ: {mode}")
        return self

    def camera_issue(self, seconds: float) -> "PoseSequence":
        for _ in range(self._n(seconds)):
            self._emit(self.body.person(self.image_size), source_ok=False)
        return self

    # ---- người khác ----

    def add_person_outside_roi(self, body: Body = NURSE) -> "PoseSequence":
        """Thêm người (đứng trước bệnh nhân trong danh sách) cho các frame sinh sau đó."""
        self._extras.append(body)
        return self

    def add_second_person_in_roi(self, body: Body | None = None) -> "PoseSequence":
        self._extras.append(body or SITTING.moved_to((420, 330)))
        return self

    def remove_extra_people(self) -> "PoseSequence":
        self._extras.clear()
        return self

    def build(self) -> list[FrameObservation]:
        return list(self._frames)
