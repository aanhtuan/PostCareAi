"""Bước 5: state machine 7 trạng thái cơ thể (F14; event-engine.md mục 4).

- Ứng viên (từ `posture.py`) phải giữ **liên tục** ≥ `min_duration_s.<đích>` mới được xác lập (R6).
  Ứng viên đổi, tư thế `UNKNOWN` hoặc frame kém xen giữa → đếm lại từ đầu.
- Cổng chất lượng (F13, trong `Engine`) đóng → `NO_OBSERVATION` ngay; mất landmark không bao giờ
  dẫn tới `OUT_OF_BED` (R8). Sau khi cổng mở lại vẫn phải giữ đủ min_duration (R7).
- Mỗi lần chuyển có `explanation` (R10) và được ghi vào `history` cho F15 (R11).

Thời gian chỉ lấy từ `ts_ms` truyền vào (R1).
"""

from collections import deque
from dataclasses import dataclass

from pydantic import JsonValue

from postcare.engine.features import BodyFeatures
from postcare.engine.pipeline import FrameAssessment
from postcare.engine.posture import (
    Location,
    Posture,
    candidate_state,
    classify_location,
    classify_posture,
)
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.state import BodyState, ObservationQuality

MS_PER_S = 1000
HISTORY_SIZE = 32
"""Số trạng thái ổn định gần nhất giữ lại cho F15 (kích thước bộ đệm, không phải ngưỡng)."""

ANOMALY_SKIPPED_EDGE = "skipped_edge"
IN_BED_STATES = frozenset({BodyState.LYING, BodyState.RAISING, BodyState.SITTING})
"""Trạng thái trong giường (dùng cho skipped_edge và F15 BED_EDGE)."""
EXIT_PATH_STATES = frozenset({BodyState.AT_EDGE, BodyState.STANDING})
"""Điều kiện trước OUT_OF_BED cho BED_EXIT (F15): đi qua AT_EDGE hoặc STANDING (R9)."""

Explanation = dict[str, JsonValue]


@dataclass(frozen=True)
class StateRecord:
    """Một trạng thái ổn định đã xác lập."""

    state: BodyState
    since_ms: int
    explanation: Explanation


class BodyStateMachine:
    """Trạng thái cơ thể ổn định với hysteresis + min_duration. Khởi tạo ở `NO_OBSERVATION`."""

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        self.state = BodyState.NO_OBSERVATION
        self.explanation: Explanation | None = None
        """Explanation của lần chuyển gần nhất; None khi chưa chuyển lần nào."""
        self._history: deque[StateRecord] = deque(maxlen=HISTORY_SIZE)
        self._candidate: BodyState | None = None
        self._candidate_since_ms = 0
        self._bad_since_ms: int | None = None
        self._ref_torso: float | None = None
        """`torso_length` lúc nằm, tham chiếu cho tỷ lệ thân (event-engine.md mục 6)."""

    @property
    def history(self) -> tuple[StateRecord, ...]:
        return tuple(self._history)

    def update(self, assessment: FrameAssessment, ts_ms: int) -> BodyState:
        """Frame chất lượng `GOOD` khi cổng chất lượng mở (Engine bảo đảm)."""
        f = assessment.features
        if f is None:
            return self.interrupt(ts_ms)
        self._bad_since_ms = None
        posture = classify_posture(f, self.state, self._ref_torso, self._config)
        location = classify_location(f, self.state, self._config)
        if self.state == BodyState.LYING and posture == Posture.LYING:
            self._ref_torso = f.torso_length
        target = candidate_state(posture, location)
        if target is None or target == self.state:
            self._candidate = None
            return self.state
        if target != self._candidate:
            self._candidate = target
            self._candidate_since_ms = ts_ms
        held_ms = ts_ms - self._candidate_since_ms
        if held_ms >= self._min_duration_ms(target):
            self._transition(
                target, ts_ms, self._feature_explanation(f, posture, location, held_ms, target)
            )
        return self.state

    def interrupt(self, ts_ms: int) -> BodyState:
        """Frame kém khi cổng còn mở: giữ trạng thái, ứng viên không còn "liên tục" (R6)."""
        self._candidate = None
        if self._bad_since_ms is None:
            self._bad_since_ms = ts_ms
        return self.state

    def lose_observation(self, quality: ObservationQuality, ts_ms: int) -> BodyState:
        """Cổng chất lượng đóng → `NO_OBSERVATION` (R5 mục 1, R8)."""
        self._candidate = None
        self._ref_torso = None
        if self.state != BodyState.NO_OBSERVATION:
            since = self._bad_since_ms if self._bad_since_ms is not None else ts_ms
            self._transition(
                BodyState.NO_OBSERVATION,
                ts_ms,
                self._base_explanation(BodyState.NO_OBSERVATION, ts_ms - since, quality),
            )
        self._bad_since_ms = None
        return self.state

    # ---- nội bộ ----

    def _min_duration_ms(self, target: BodyState) -> float:
        return float(getattr(self._config.min_duration_s, target.value)) * MS_PER_S

    def _base_explanation(
        self, target: BodyState, held_ms: int, quality: ObservationQuality
    ) -> Explanation:
        return {
            "rule_id": f"state.{target.value.lower()}",
            "from_state": self.state.value,
            "to_state": target.value,
            "held_ms": held_ms,
            "observation_quality": quality.value,
        }

    def _feature_explanation(
        self,
        f: BodyFeatures,
        posture: Posture,
        location: Location,
        held_ms: int,
        target: BodyState,
    ) -> Explanation:
        exp = self._base_explanation(target, held_ms, ObservationQuality.GOOD)
        ratio = f.torso_length / self._ref_torso if self._ref_torso else None
        exp.update(
            {
                "posture": posture.value,
                "location": location.value,
                "trunk_angle_deg": round(f.trunk_angle_deg, 1),
                "dist_to_roi_edge": round(f.dist_to_roi_edge, 3),
                "ankles_outside_roi": f.ankles_outside_roi,
                "torso_length_ratio": None if ratio is None else round(ratio, 3),
            }
        )
        if target == BodyState.OUT_OF_BED and self._skipped_edge():
            exp["anomaly"] = ANOMALY_SKIPPED_EDGE
        return exp

    def _skipped_edge(self) -> bool:
        """Ra ngoài thẳng từ LYING/RAISING/SITTING, không qua AT_EDGE hay STANDING (R9).

        Đoạn NO_OBSERVATION xen giữa được bỏ qua (event-engine.md mục 4).
        """
        for record in reversed(self._history):
            if record.state == BodyState.NO_OBSERVATION:
                continue
            if record.state in EXIT_PATH_STATES:
                return False
            return record.state in IN_BED_STATES
        return False

    def _transition(self, target: BodyState, ts_ms: int, explanation: Explanation) -> None:
        self.state = target
        self.explanation = explanation
        self._candidate = None
        self._history.append(StateRecord(target, ts_ms, explanation))
