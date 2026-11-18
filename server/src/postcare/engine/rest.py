"""Bước 8b: trạng thái nghỉ/hoạt động **tham khảo** (F27 R1–R5; event-engine.md mục 3, 5).

Không phải phân loại giấc ngủ, không thay đánh giá y khoa, không sinh sự kiện hay cảnh báo
(PDF §4.2; HS §9.1). Chỉ mô tả mức hoạt động quan sát được từ `activity_level` (F23) và tín hiệu
`eyes_closed` (F26). Thời gian chỉ lấy từ `ts_ms`.

Quy tắc mỗi frame, theo thứ tự *(giả định F27 mục 9)*:

1. `body_state = NO_OBSERVATION` hoặc `activity_level = UNKNOWN` → `UNKNOWN` ngay.
2. `activity_level = LOW` mà `face_status ≠ OK` → `UNKNOWN` ngay, kể cả đang `RESTING`: mặt không
   rõ thì không bao giờ kết luận "đang nghỉ" (R4). Đang `RESTING` mà `face_status ≠ OK` →
   `UNKNOWN` ngay, bất kể mức vận động (review F27).
3. `LOW` liên tục ≥ `rest.low_activity_s` và `eyes_closed` (mặt `OK`) liên tục ≥
   `rest.eyes_closed_s` → `RESTING` (R1).
4. Ứng viên hoạt động (`activity_level ≠ LOW`, hoặc `LOW` + mặt `OK` + mắt mở): từ `UNKNOWN` /
   `ACTIVE` → `ACTIVE` ngay (R3; mức vận động đã có cửa sổ riêng); từ `RESTING` phải giữ liên tục
   ≥ `rest.active_hold_s` (R2, "không tin một frame").
5. Còn lại (`LOW` + mặt `OK` + mắt đóng chưa đủ lâu) → giữ trạng thái hiện tại.

Mỗi lần chuyển ghi một entry mức LOG vào `RestReading.explanation` (R5).
"""

from dataclasses import dataclass

from postcare.engine.activity import ActivityReading
from postcare.engine.face import FaceReading
from postcare.engine.state_machine import Explanation
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.enums import Priority
from postcare.schemas.state import ActivityLevel, BodyState, FaceStatus, RestStatus

MS_PER_S = 1000


@dataclass(frozen=True)
class RestReading:
    status: RestStatus
    explanation: Explanation | None
    """Entry LOG của lần chuyển `rest_status` gần nhất; None khi chưa chuyển lần nào."""


class RestTracker:
    """Một instance cho một `Engine`."""

    def __init__(self, config: EngineConfig) -> None:
        rest = config.rest
        self._low_ms = rest.low_activity_s * MS_PER_S
        self._eyes_ms = rest.eyes_closed_s * MS_PER_S
        self._hold_ms = rest.active_hold_s * MS_PER_S
        self._low_since: int | None = None
        self._eyes_since: int | None = None
        self._active_since: int | None = None
        self._reading = RestReading(status=RestStatus.UNKNOWN, explanation=None)

    @property
    def reading(self) -> RestReading:
        return self._reading

    def update(
        self,
        ts_ms: int,
        body_state: BodyState,
        activity: ActivityReading,
        face: FaceReading,
    ) -> RestReading:
        observed = (
            body_state != BodyState.NO_OBSERVATION and activity.level != ActivityLevel.UNKNOWN
        )
        low = observed and activity.level == ActivityLevel.LOW
        face_ok = face.status == FaceStatus.OK
        eyes_closed = face_ok and face.signals.eyes_closed

        self._low_since = (
            (self._low_since if self._low_since is not None else ts_ms) if low else None
        )
        if eyes_closed:
            self._eyes_since = self._eyes_since if self._eyes_since is not None else ts_ms
        else:
            self._eyes_since = None
        low_ms = 0 if self._low_since is None else ts_ms - self._low_since
        eyes_ms = 0 if self._eyes_since is None else ts_ms - self._eyes_since

        current = self._reading.status
        active_candidate = observed and (not low or (face_ok and not eyes_closed))
        if active_candidate:
            self._active_since = self._active_since if self._active_since is not None else ts_ms
        else:
            self._active_since = None

        lost_face_while_resting = current == RestStatus.RESTING and not face_ok
        if not observed or (low and not face_ok) or lost_face_while_resting:
            target = RestStatus.UNKNOWN
        elif low and low_ms >= self._low_ms and eyes_ms >= self._eyes_ms:
            target = RestStatus.RESTING
        elif active_candidate:
            held = 0 if self._active_since is None else ts_ms - self._active_since
            if current != RestStatus.RESTING or held >= self._hold_ms:
                target = RestStatus.ACTIVE
            else:
                target = current
        else:
            target = current

        if target != current:
            self._reading = RestReading(
                status=target,
                explanation={
                    "rule_id": f"rest.{target.value.lower()}",
                    "priority": Priority.LOG.value,
                    "from_status": current.value,
                    "to_status": target.value,
                    "activity_level": activity.level.value,
                    "face_status": face.status.value,
                    "low_activity_ms": low_ms,
                    "eyes_closed_ms": eyes_ms,
                    "ts_ms": ts_ms,
                },
            )
        return self._reading
