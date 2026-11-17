"""Trạng thái hiển thị do engine suy ra (event-engine.md mục 2, 4, 5).

Enum trạng thái nằm ở `schemas/enums.py` (một nguồn sự thật, DB và API cũng dùng); module này
xuất lại để engine import từ một chỗ.
"""

from pydantic import BaseModel, ConfigDict, JsonValue

from postcare.schemas.enums import (
    ActivityLevel,
    BodyState,
    FaceStatus,
    ObservationQuality,
    RestStatus,
)

__all__ = [
    "ActivityLevel",
    "BodyState",
    "BodyStateSnapshot",
    "FaceSignals",
    "FaceStatus",
    "ObservationQuality",
    "RestStatus",
]


class FaceSignals(BaseModel):
    """Tín hiệu khuôn mặt engine suy ra theo thời gian (F26 điền). Mặc định: không có tín hiệu."""

    model_config = ConfigDict(frozen=True)

    eyes_closed: bool = False
    eyes_closed_prolonged: bool = False
    brow_down: bool = False
    eye_squint: bool = False
    nose_sneer: bool = False
    mouth_change: bool = False


class BodyStateSnapshot(BaseModel):
    """Trạng thái hiện tại của người mục tiêu, gửi lên API khi thay đổi."""

    model_config = ConfigDict(frozen=True)

    body_state: BodyState
    observation_quality: ObservationQuality
    activity_level: ActivityLevel
    rest_status: RestStatus
    face_status: FaceStatus
    face_signals: FaceSignals
    explanation: dict[str, JsonValue] | None = None
    """Căn cứ của lần chuyển `body_state` gần nhất (F14 R10): `rule_id`, `from_state`, `to_state`,
    `held_ms`, đặc trưng chính, có thể có `anomaly`. None ở trạng thái khởi tạo."""
