"""Catalog sự kiện (event-engine.md mục 5). Bảng trong tài liệu phải khớp file này."""

from dataclasses import dataclass
from enum import StrEnum

from postcare.schemas.enums import PRIORITY_RANK, Priority


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
    return min(EVENT_CATALOG[code].allowed_priorities, key=lambda p: PRIORITY_RANK[p])
