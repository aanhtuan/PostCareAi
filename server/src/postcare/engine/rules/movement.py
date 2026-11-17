"""Bước 7b: sự kiện vận động (F23 R5–R10; event-engine.md mục 5; ADR-0009).

- `ACTIVITY_INCREASED` (LOG): `activity_level` vào `HIGH` và giữ ≥ `activity.increased_hold_s`.
- `ACTIVITY_LOW_PROLONGED` (LOG): `activity_level = LOW` liên tục ≥ `activity.low_prolonged_s`.
  Mỗi đoạn mức liên tục phát tối đa một lần; `UNKNOWN` (mất quan sát) cắt đoạn (R4, R6).
- `ABNORMAL_MOVEMENT` (HIGH): ≥ `abnormal_movement.min_conditions` trong 5 điều kiện C1–C5 (R7),
  chỉ trên chuỗi frame `GOOD` liên tục của cùng một người mục tiêu (R8). Không xét ROI: mục tiêu
  đã ra ngoài giường (nằm trên sàn cạnh giường) vẫn được xét.

Cách xét `ABNORMAL_MOVEMENT` *(giả định F23 R7, ghi ở event-engine.md mục 5)*:

1. Mỗi frame `t` có mẫu tham chiếu `ref(t)` = mẫu mới nhất cách ≥ `window_s` về trước (thiếu →
   frame chưa xét được). Dấu hiệu nhanh ở `t`: F1 = max vận tốc đi xuống của `hip_center` trong
   `(t − window_s, t]` ≥ `hip_drop_speed_torso_per_s` (vận tốc chia torso lớn hơn giữa frame và
   mốc); F2 = `|hip(t) − hip(ref)| / torso(ref)` ≥
   `displacement_torso`; F3 = `|trunk(t) − trunk(ref)|` ≥ `trunk_angle_change_deg`.
2. Có dấu hiệu nhanh → mở / kéo dài một "chuyển động". Mẫu "trước" = `ref` của frame có nhiều
   dấu hiệu nhất (frame đầu tiên đạt số đó). Hết dấu hiệu → bắt đầu đếm `hold_after_s`; dấu hiệu
   quay lại thì đếm lại.
3. Đủ `hold_after_s` → chấm điểm với vị trí **cuối** (frame hiện tại), để nhiễu 1–3 frame rồi
   quay về không được tính là dịch chuyển: C1 = vận tốc đi xuống lớn nhất trong chuyển động;
   C2, C3 = so vị trí / góc thân cuối với mẫu "trước"; C4 = `hip_y` cuối / chiều cao khung hình ≥
   `final_low_position_ratio`; C5 = trung vị tốc độ mẫu vận động (cùng cách tính với chỉ số vận
   động, `engine/activity.py`) trong khoảng giữ < `activity.low_threshold`.
   Đủ `min_conditions` → phát.

`occurred_at_ms` = mẫu đầu tiên trong chuyển động có tốc độ hông ≥ `hip_drop_speed_torso_per_s`,
không có thì frame đầu có dấu hiệu nhanh. `detected_at_ms` = lúc chấm điểm.
"""

import statistics
from collections import deque
from dataclasses import dataclass, field

from pydantic import JsonValue

from postcare.engine.activity import ActivityReading
from postcare.engine.features import BodyFeatures
from postcare.engine.geometry import Px, distance
from postcare.engine.pipeline import FrameAssessment
from postcare.engine.rules.common import MS_PER_S, EventDraft, Explanation, VisibilityBuffer
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.events import EventCode
from postcare.schemas.state import ActivityLevel, ObservationQuality

_BUFFER_SLACK_MS = 1000
"""Dư cho bộ đệm visibility (không phải ngưỡng)."""

CONDITIONS = (
    "hip_drop_speed",
    "displacement",
    "trunk_angle_change",
    "final_low_position",
    "still_after",
)
"""C1–C5, theo thứ tự ghi trong `explanation.conditions_met`."""


@dataclass(frozen=True)
class _Sample:
    ts_ms: int
    hip: Px
    torso: float
    trunk_deg: float
    vy: float
    """Vận tốc dọc của hông (torso/s, dương = đi xuống ảnh)."""
    speed: float
    """Độ lớn vận tốc hông (torso/s)."""
    height: int
    ref: "_Sample | None"
    """Mẫu cách ≥ window_s về trước; None khi frame chưa xét được."""


@dataclass
class _Motion:
    before: _Sample
    best_signs: int
    peak_vy: float
    occurred_ms: int
    last_sign_ms: int
    hold_speeds: list[float] = field(default_factory=list)


def _r(value: float, digits: int = 3) -> float:
    return round(value, digits)


class MovementRules:
    """Một instance cho một `Engine`; kết quả chưa debounce (`RuleSet` lọc)."""

    def __init__(self, config: EngineConfig) -> None:
        act = config.activity
        am = config.abnormal_movement
        self._act = act
        self._am = am
        self._increased_hold_ms = act.increased_hold_s * MS_PER_S
        self._low_prolonged_ms = act.low_prolonged_s * MS_PER_S
        self._window_ms = am.window_s * MS_PER_S
        self._hold_ms = am.hold_after_s * MS_PER_S
        horizon_s = max(
            act.low_prolonged_s,
            act.increased_hold_s + act.window_s,
            2 * am.window_s + am.hold_after_s,
        )
        self._visibility = VisibilityBuffer(
            config.pose.required_keypoints, horizon_s * MS_PER_S + _BUFFER_SLACK_MS
        )
        # ACTIVITY_* (R5, R6)
        self._segment_level = ActivityLevel.UNKNOWN
        self._segment_start_ms = 0
        self._segment_emitted = False
        # ABNORMAL_MOVEMENT (R7, R8)
        self._samples: deque[_Sample] = deque()
        self._motion: _Motion | None = None

    def evaluate(
        self, ts_ms: int, assessment: FrameAssessment, activity: ActivityReading
    ) -> list[EventDraft]:
        self._visibility.record(ts_ms, assessment.target)
        drafts: list[EventDraft] = []
        drafts.extend(self._activity_events(ts_ms, assessment.quality, activity))
        drafts.extend(self._abnormal_movement(ts_ms, assessment, activity))
        return drafts

    # ---- R5, R6 ----

    def _activity_events(
        self, ts_ms: int, quality: ObservationQuality, activity: ActivityReading
    ) -> list[EventDraft]:
        level = activity.level
        if level != self._segment_level:
            self._segment_level = level
            self._segment_start_ms = ts_ms
            self._segment_emitted = False
        if self._segment_emitted or activity.index is None:
            return []
        held_ms = ts_ms - self._segment_start_ms
        if level == ActivityLevel.HIGH and held_ms >= self._increased_hold_ms:
            code, threshold = EventCode.ACTIVITY_INCREASED, self._act.high_threshold
        elif level == ActivityLevel.LOW and held_ms >= self._low_prolonged_ms:
            code, threshold = EventCode.ACTIVITY_LOW_PROLONGED, self._act.low_threshold
        else:
            return []
        self._segment_emitted = True
        explanation: Explanation = {
            "rule_id": _rule_id(code),
            "activity_level": level.value,
            "activity_index": _r(activity.index),
            "threshold": threshold,
            "held_ms": held_ms,
            "window_s": self._act.window_s,
        }
        return [self._draft(code, self._segment_start_ms, ts_ms, quality, explanation)]

    # ---- R7, R8 ----

    def _reset_motion(self) -> None:
        self._samples.clear()
        self._motion = None

    def _abnormal_movement(
        self, ts_ms: int, assessment: FrameAssessment, activity: ActivityReading
    ) -> list[EventDraft]:
        f = assessment.features
        if not assessment.observable or f is None:
            # R8: cửa sổ không được chứa frame không GOOD hoặc NO_OBSERVATION
            self._reset_motion()
            return []
        if assessment.target_is_new:
            # R8: bước nhảy do đổi người không phải chuyển động; chuỗi mới bắt đầu từ frame này
            self._reset_motion()
        sample = self._append(ts_ms, f)
        if sample.ref is None:
            return []
        signs, window_peak_vy = self._fast_signs(sample)
        motion = self._motion
        if signs > 0:
            if motion is None:
                motion = _Motion(
                    before=sample.ref,
                    best_signs=signs,
                    peak_vy=window_peak_vy,
                    occurred_ms=self._fast_start(sample),
                    last_sign_ms=ts_ms,
                )
                self._motion = motion
            else:
                if signs > motion.best_signs:
                    motion.before = sample.ref
                    motion.best_signs = signs
                motion.peak_vy = max(motion.peak_vy, window_peak_vy)
                motion.last_sign_ms = ts_ms
                motion.hold_speeds.clear()
            return []
        if motion is None:
            return []
        if activity.sample_speed is not None:
            motion.hold_speeds.append(activity.sample_speed)
        if ts_ms - motion.last_sign_ms < self._hold_ms:
            return []
        self._motion = None
        return self._score(ts_ms, assessment.quality, motion, sample)

    def _append(self, ts_ms: int, f: BodyFeatures) -> _Sample:
        ref: _Sample | None = None
        for s in reversed(self._samples):
            if s.ts_ms <= ts_ms - self._window_ms:
                ref = s
                break
        # Vận tốc của F13 chia torso của chính frame; thân co ngắn (phối cảnh, keypoint lỗi) sẽ thổi
        # phồng vận tốc. Chuẩn hóa lại theo torso lớn hơn giữa frame này và mốc.
        torso = max(f.torso_length, ref.torso) if ref is not None else f.torso_length
        scale = f.torso_length / torso if torso > 0 else 0.0
        vx, vy = f.velocity[0] * scale, f.velocity[1] * scale
        sample = _Sample(
            ts_ms=ts_ms,
            hip=f.hip_center,
            torso=f.torso_length,
            trunk_deg=f.trunk_angle_deg,
            vy=vy,
            speed=(vx * vx + vy * vy) ** 0.5,
            height=f.image_size[1],
            ref=_strip(ref),
        )
        self._samples.append(sample)
        # Giữ các mẫu trong cửa sổ + một mẫu làm mốc
        while len(self._samples) >= 2 and self._samples[1].ts_ms <= ts_ms - self._window_ms:
            self._samples.popleft()
        return sample

    def _window(self, sample: _Sample) -> list[_Sample]:
        """Các mẫu xét được trong `(t − window_s, t]`."""
        lo = sample.ts_ms - self._window_ms
        return [s for s in self._samples if s.ts_ms > lo and s.ref is not None]

    def _fast_signs(self, sample: _Sample) -> tuple[int, float]:
        ref = sample.ref
        assert ref is not None
        peak_vy = max((s.vy for s in self._window(sample)), default=0.0)
        f1 = peak_vy >= self._am.hip_drop_speed_torso_per_s
        f2 = _displacement(ref, sample) >= self._am.displacement_torso
        f3 = abs(sample.trunk_deg - ref.trunk_deg) >= self._am.trunk_angle_change_deg
        return int(f1) + int(f2) + int(f3), peak_vy

    def _fast_start(self, sample: _Sample) -> int:
        for s in self._window(sample):
            if s.speed >= self._am.hip_drop_speed_torso_per_s:
                return s.ts_ms
        return sample.ts_ms

    def _score(
        self, ts_ms: int, quality: ObservationQuality, motion: _Motion, final: _Sample
    ) -> list[EventDraft]:
        am = self._am
        before = motion.before
        displacement = _displacement(before, final)
        trunk_change = abs(final.trunk_deg - before.trunk_deg)
        position_ratio = final.hip[1] / final.height if final.height > 0 else 0.0
        still: float | None = None
        if motion.hold_speeds:
            still = statistics.median(motion.hold_speeds)
        met = {
            "hip_drop_speed": motion.peak_vy >= am.hip_drop_speed_torso_per_s,
            "displacement": displacement >= am.displacement_torso,
            "trunk_angle_change": trunk_change >= am.trunk_angle_change_deg,
            "final_low_position": position_ratio >= am.final_low_position_ratio,
            "still_after": am.hold_after_s > 0
            and still is not None
            and still < self._act.low_threshold,
        }
        conditions_met: list[JsonValue] = [name for name in CONDITIONS if met[name]]
        if len(conditions_met) < am.min_conditions:
            return []
        explanation: Explanation = {
            "rule_id": _rule_id(EventCode.ABNORMAL_MOVEMENT),
            "conditions_met": conditions_met,
            "min_conditions": am.min_conditions,
            "hip_drop_speed_torso_per_s": _r(motion.peak_vy),
            "displacement_torso": _r(displacement),
            "trunk_angle_change_deg": _r(trunk_change, 1),
            "final_position_ratio": _r(position_ratio),
            "activity_index_after": None if still is None else _r(still),
            "window_s": am.window_s,
            "hold_after_s": am.hold_after_s,
            "held_ms": ts_ms - motion.last_sign_ms,
        }
        return [
            self._draft(
                EventCode.ABNORMAL_MOVEMENT, motion.occurred_ms, ts_ms, quality, explanation
            )
        ]

    def _draft(
        self,
        code: EventCode,
        occurred_ms: int,
        detected_ms: int,
        quality: ObservationQuality,
        explanation: Explanation,
    ) -> EventDraft:
        return EventDraft(
            code=code,
            occurred_at_ms=occurred_ms,
            detected_at_ms=detected_ms,
            confidence=self._visibility.confidence(occurred_ms, detected_ms),
            observation_quality=quality,
            explanation=explanation,
        )


def _strip(sample: _Sample | None) -> _Sample | None:
    """Bỏ liên kết `ref` lồng nhau để chuỗi mốc không giữ mẫu cũ trong bộ nhớ."""
    if sample is None or sample.ref is None:
        return sample
    return _Sample(
        ts_ms=sample.ts_ms,
        hip=sample.hip,
        torso=sample.torso,
        trunk_deg=sample.trunk_deg,
        vy=sample.vy,
        speed=sample.speed,
        height=sample.height,
        ref=None,
    )


def _displacement(before: _Sample, after: _Sample) -> float:
    return distance(before.hip, after.hip) / before.torso if before.torso > 0 else 0.0


def _rule_id(code: EventCode) -> str:
    return f"movement.{code.value.lower()}"
