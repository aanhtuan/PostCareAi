"""Bước 8a: tín hiệu khuôn mặt theo thời gian từ blendshape (F26 R1–R3; event-engine.md mục 8).

- Mỗi tín hiệu trong `face.signals` = **max** các khóa blendshape của nó, làm mượt EMA với
  `smoothing.ema_alpha`, bật khi ≥ `threshold` *(giả định F26 R1)*.
- `eyes_closed_prolonged`: `eyes_closed` bật liên tục ≥ `face.eyes_closed_prolonged_s` (R2). Chỉ để
  hiển thị; khi đếm cho FACE_ATTENTION nhóm mắt tính một tín hiệu.
- `face = None` (frame không chạy face): giữ giá trị gần nhất. `status ≠ OK`, mất quan sát cơ thể
  hoặc đổi người mục tiêu: xóa mọi tín hiệu và bộ đếm (R3). Thiếu dữ liệu mặt **không** bao giờ được
  coi là bình thường (HS §9.1).

Không gán nhãn đau, ngủ hay mất ý thức: đây chỉ là tín hiệu quan sát (PDF §6.2).
"""

from dataclasses import dataclass

from postcare.schemas.engine_config import EngineConfig, FaceSignalsConfig
from postcare.schemas.observation import FaceObservation
from postcare.schemas.state import FaceSignals, FaceStatus

MS_PER_S = 1000

SIGNAL_NAMES: tuple[str, ...] = tuple(FaceSignalsConfig.model_fields)
"""Tín hiệu cơ bản theo thứ tự `face.signals` (đếm cho FACE_ATTENTION)."""


@dataclass(frozen=True)
class FaceReading:
    """Kết quả bước 8a cho một khung hình."""

    status: FaceStatus
    signals: FaceSignals
    values: dict[str, float]
    """Giá trị đã làm mượt của các tín hiệu đang có dữ liệu (làm tròn 3 chữ số)."""

    @property
    def active(self) -> tuple[str, ...]:
        """Tín hiệu đang bật, gồm cả `eyes_closed_prolonged` (để hiển thị/giải thích)."""
        flags = self.signals.model_dump()
        return tuple(name for name, on in flags.items() if on)

    @property
    def attention_count(self) -> int:
        """Số tín hiệu đếm cho FACE_ATTENTION: nhóm mắt chỉ một (R2)."""
        flags = self.signals.model_dump()
        return sum(1 for name in SIGNAL_NAMES if flags[name])


NO_FACE = FaceReading(status=FaceStatus.NOT_VISIBLE, signals=FaceSignals(), values={})


class FaceTracker:
    """Một instance cho một `Engine`. Thời gian chỉ lấy từ `ts_ms`."""

    def __init__(self, config: EngineConfig) -> None:
        sig = config.face.signals
        self._alpha = config.smoothing.ema_alpha
        self._specs = {name: getattr(sig, name) for name in SIGNAL_NAMES}
        self._prolonged_ms = config.face.eyes_closed_prolonged_s * MS_PER_S
        self._smoothed: dict[str, float] = {}
        self._eyes_closed_since_ms: int | None = None
        self._reading = NO_FACE

    @property
    def reading(self) -> FaceReading:
        return self._reading

    def reset(self, status: FaceStatus = FaceStatus.NOT_VISIBLE) -> FaceReading:
        self._smoothed.clear()
        self._eyes_closed_since_ms = None
        self._reading = FaceReading(status=status, signals=FaceSignals(), values={})
        return self._reading

    def update(self, ts_ms: int, face: FaceObservation | None) -> FaceReading:
        if face is None:
            return self._hold(ts_ms)
        if face.status != FaceStatus.OK:
            return self.reset(face.status)
        a = self._alpha
        for name, spec in self._specs.items():
            present = [face.blendshapes[k] for k in spec.keys if k in face.blendshapes]
            if not present:
                # Khóa vắng mặt ở frame OK → tín hiệu tắt, bỏ giá trị cũ (giả định F26).
                self._smoothed.pop(name, None)
                continue
            raw = max(present)
            prev = self._smoothed.get(name)
            self._smoothed[name] = raw if prev is None else a * raw + (1 - a) * prev
        return self._evaluate(ts_ms, FaceStatus.OK)

    def _hold(self, ts_ms: int) -> FaceReading:
        if self._reading.status != FaceStatus.OK:
            return self._reading
        # Giữ giá trị gần nhất nhưng thời gian nhắm mắt vẫn trôi theo `ts_ms`.
        return self._evaluate(ts_ms, FaceStatus.OK)

    def _evaluate(self, ts_ms: int, status: FaceStatus) -> FaceReading:
        on = {
            name: (v := self._smoothed.get(name)) is not None and v >= self._specs[name].threshold
            for name in SIGNAL_NAMES
        }
        if on["eyes_closed"]:
            if self._eyes_closed_since_ms is None:
                self._eyes_closed_since_ms = ts_ms
        else:
            self._eyes_closed_since_ms = None
        prolonged = (
            self._eyes_closed_since_ms is not None
            and ts_ms - self._eyes_closed_since_ms >= self._prolonged_ms
        )
        self._reading = FaceReading(
            status=status,
            signals=FaceSignals(eyes_closed_prolonged=prolonged, **on),
            values={name: round(v, 3) for name, v in self._smoothed.items()},
        )
        return self._reading
