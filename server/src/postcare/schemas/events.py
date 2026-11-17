"""Catalog sự kiện (event-engine.md mục 5). Bảng trong tài liệu phải khớp file này."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from postcare.schemas.enums import PRIORITY_RANK, ObservationQuality, Priority
from postcare.schemas.state import BodyStateSnapshot


class EventCode(StrEnum):
    POSTURE_CHANGE = "POSTURE_CHANGE"
    SIT_UP = "SIT_UP"
    STAND_UP = "STAND_UP"
    BED_EDGE = "BED_EDGE"
    BED_EXIT = "BED_EXIT"
    RETURN_TO_BED = "RETURN_TO_BED"
    ACTIVITY_INCREASED = "ACTIVITY_INCREASED"
    ACTIVITY_LOW_PROLONGED = "ACTIVITY_LOW_PROLONGED"
    ABNORMAL_MOVEMENT = "ABNORMAL_MOVEMENT"
    FACE_ATTENTION = "FACE_ATTENTION"
    OBSERVATION_LOST = "OBSERVATION_LOST"
    OBSERVATION_RESTORED = "OBSERVATION_RESTORED"
    CAMERA_OFFLINE = "CAMERA_OFFLINE"
    CAMERA_ONLINE = "CAMERA_ONLINE"


@dataclass(frozen=True)
class EventSpec:
    """Mức ưu tiên cho phép của một mã sự kiện và nơi sinh ra nó."""

    allowed_priorities: frozenset[Priority]
    api_generated: bool = False

    @property
    def default_priority(self) -> Priority:
        """Mức mặc định = mức thấp nhất cho phép (FACE_ATTENTION: MEDIUM; F26 nâng lên HIGH)."""
        return min(self.allowed_priorities, key=lambda p: PRIORITY_RANK[p])

    @property
    def creates_alert(self) -> bool:
        """Mức mặc định MEDIUM/HIGH thì tạo cảnh báo PENDING (QA#17)."""
        return self.default_priority in ALERT_PRIORITIES


def _one(priority: Priority, *, api_generated: bool = False) -> EventSpec:
    return EventSpec(frozenset({priority}), api_generated)


EVENT_CATALOG: dict[EventCode, EventSpec] = {
    EventCode.POSTURE_CHANGE: _one(Priority.LOG),
    EventCode.SIT_UP: _one(Priority.INFO),
    EventCode.STAND_UP: _one(Priority.INFO),
    EventCode.BED_EDGE: _one(Priority.MEDIUM),
    EventCode.BED_EXIT: _one(Priority.HIGH),
    EventCode.RETURN_TO_BED: _one(Priority.INFO),
    EventCode.ACTIVITY_INCREASED: _one(Priority.LOG),
    EventCode.ACTIVITY_LOW_PROLONGED: _one(Priority.LOG),
    EventCode.ABNORMAL_MOVEMENT: _one(Priority.HIGH),
    EventCode.FACE_ATTENTION: EventSpec(frozenset({Priority.MEDIUM, Priority.HIGH})),
    EventCode.OBSERVATION_LOST: _one(Priority.INFO),
    EventCode.OBSERVATION_RESTORED: _one(Priority.LOG),
    EventCode.CAMERA_OFFLINE: _one(Priority.MEDIUM, api_generated=True),
    EventCode.CAMERA_ONLINE: _one(Priority.LOG, api_generated=True),
}

# Mức ưu tiên tạo cảnh báo cần tiếp nhận (QA#17).
ALERT_PRIORITIES: frozenset[Priority] = frozenset({Priority.MEDIUM, Priority.HIGH})

# Sự kiện tư thế/vị trí dùng làm "số lần đổi trạng thái" ở bàn giao ca (F24 R3, giả định).
STATE_CHANGE_CODES: frozenset[EventCode] = frozenset(
    {
        EventCode.POSTURE_CHANGE,
        EventCode.SIT_UP,
        EventCode.STAND_UP,
        EventCode.BED_EDGE,
        EventCode.BED_EXIT,
        EventCode.RETURN_TO_BED,
    }
)


def default_priority(code: EventCode) -> Priority:
    """Mức ưu tiên mặc định (thấp nhất trong các mức cho phép)."""
    return EVENT_CATALOG[code].default_priority


class EngineEvent(BaseModel):
    """Một sự kiện engine phát ra (event-engine.md mục 2, 5)."""

    model_config = ConfigDict(frozen=True)

    code: EventCode
    priority: Priority
    occurred_at_ms: Annotated[int, Field(ge=0)]
    """Lúc hành động bắt đầu (theo `ts_ms`)."""
    detected_at_ms: Annotated[int, Field(ge=0)]
    """Lúc engine kết luận, sau khi đủ `min_duration` (theo `ts_ms`)."""
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    observation_quality: ObservationQuality
    explanation: dict[str, JsonValue]
    """Căn cứ ngắn gọn: luôn có `rule_id` và giá trị đặc trưng chính (PDF §7; HS §6.2)."""

    @model_validator(mode="after")
    def _check(self) -> Self:
        rule_id = self.explanation.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError("explanation.rule_id phải là chuỗi không rỗng")
        if self.priority not in EVENT_CATALOG[self.code].allowed_priorities:
            raise ValueError(f"priority {self.priority} không hợp lệ cho {self.code}")
        if self.occurred_at_ms > self.detected_at_ms:
            raise ValueError("occurred_at_ms phải ≤ detected_at_ms")
        return self


class EngineOutput(BaseModel):
    """Kết quả của `Engine.process(obs)` cho một khung hình."""

    model_config = ConfigDict(frozen=True)

    state: BodyStateSnapshot
    state_changed: bool
    events: list[EngineEvent] = Field(default_factory=list)
