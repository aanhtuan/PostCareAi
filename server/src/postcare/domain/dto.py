"""Schema request/response (`<Resource>Out`, `<Resource>Create`) và hàm chuyển từ model DB.

API không trả câu tiếng Việt cho sự kiện; frontend ánh xạ mã → câu (api-conventions.md).
"""

import re
from datetime import datetime, time
from fnmatch import fnmatchcase
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from postcare.db.models import (
    Alert,
    Area,
    Bed,
    Camera,
    Event,
    MonitoringSession,
    Patient,
    ShiftDefinition,
    User,
)
from postcare.schemas.enums import (
    ActivityLevel,
    AlertOutcome,
    AlertStatus,
    BodyState,
    CameraSourceType,
    CameraStatus,
    DisplayMode,
    FaceStatus,
    ObservationQuality,
    Priority,
    RestStatus,
    UserRole,
)
from postcare.schemas.events import EventCode


class StrictIn(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Page[T](BaseModel):
    items: list[T]
    total: int


# ---------- Người dùng ----------


class UserRef(BaseModel):
    id: int
    full_name: str


class UserOut(BaseModel):
    """Không bao giờ có `password_hash` (F02 R4; F35 R4; PRD NFR06)."""

    id: int
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


_USERNAME_RE = re.compile(r"[a-z0-9._-]{3,64}")


def _username(v: str) -> str:
    v = v.strip().lower()
    if not _USERNAME_RE.fullmatch(v):
        raise ValueError("Tên đăng nhập gồm 3–64 ký tự a-z, 0-9, dấu chấm, gạch dưới, gạch ngang")
    return v


def _full_name(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("Họ tên không được để trống")
    return v


def _password(v: str) -> str:
    if len(v.encode()) > 72:  # bcrypt chỉ dùng 72 byte đầu
        raise ValueError("Mật khẩu tối đa 72 byte")
    return v


# F35 R5, R6 (giả định): username bỏ khoảng trắng, chữ thường; mật khẩu tối thiểu 8 ký tự.
Username = Annotated[str, AfterValidator(_username)]
FullName = Annotated[str, Field(max_length=200), AfterValidator(_full_name)]
Password = Annotated[str, Field(min_length=8), AfterValidator(_password)]


class UserCreate(StrictIn):
    username: Username
    full_name: FullName
    role: UserRole
    password: Password


class UserUpdate(StrictIn):
    full_name: FullName | None = None
    role: UserRole | None = None


class PasswordReset(StrictIn):
    new_password: Password


class LoginIn(StrictIn):
    username: str
    password: str


class LoginOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut


def user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        username=u.username,
        full_name=u.full_name,
        role=u.role,
        is_active=u.is_active,
        created_at=u.created_at,
    )


def user_ref(u: User | None) -> UserRef | None:
    return UserRef(id=u.id, full_name=u.full_name) if u else None


# ---------- Ca trực ----------


class ShiftOut(BaseModel):
    """`end_time < start_time`: ca vắt qua nửa đêm (data-model.md)."""

    id: int
    name: str
    start_time: time
    end_time: time
    is_active: bool


def shift_out(s: ShiftDefinition) -> ShiftOut:
    return ShiftOut(
        id=s.id,
        name=s.name,
        start_time=s.start_time,
        end_time=s.end_time,
        is_active=s.is_active,
    )


# ---------- Danh mục ----------


class CameraRef(BaseModel):
    id: int
    name: str
    status: CameraStatus


class SessionOut(BaseModel):
    id: int
    bed_id: int
    bed_code: str
    patient_id: int
    patient_code: str
    camera_id: int | None
    started_at: datetime
    started_by: UserRef
    ended_at: datetime | None
    ended_by: UserRef | None
    previous_session_id: int | None
    # Mã giường của phiên trước, để UI hiện "Chuyển từ giường …" (F04 R18).
    previous_bed_code: str | None
    next_session_id: int | None
    transfer_reason: str | None
    paused_at: datetime | None
    paused_by: UserRef | None


class SessionCreate(StrictIn):
    bed_id: int
    patient_id: int


class AreaRef(BaseModel):
    id: int
    code: str
    name: str


class AreaOut(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool
    created_at: datetime
    bed_count: int  # số giường đang dùng (chưa xóa) trong khu vực


# Lý do chuyển giường bắt buộc, bỏ khoảng trắng đầu/cuối (F04 R12).
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class SessionTransfer(StrictIn):
    target_bed_id: int
    reason: Reason


class SessionPause(StrictIn):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None


class SessionChainItem(BaseModel):
    """Một phiên trong chuỗi chuyển giường, để F22 ghép timeline (F04 R16)."""

    id: int
    bed_id: int
    bed_code: str
    started_at: datetime
    ended_at: datetime | None
    previous_session_id: int | None
    transfer_reason: str | None


class BedOut(BaseModel):
    id: int
    code: str
    area: AreaRef
    is_active: bool
    camera: CameraRef | None
    active_session: SessionOut | None


class PatientOut(BaseModel):
    id: int
    code: str
    note: str | None
    is_active: bool
    active_session_id: int | None


class CameraOut(BaseModel):
    id: int
    name: str
    bed_id: int | None
    bed_code: str | None
    source_type: CameraSourceType
    source: str
    display_mode: DisplayMode
    status: CameraStatus
    last_seen_at: datetime | None
    config_version: int
    is_active: bool


class CameraRuntimeOut(BaseModel):
    """Số liệu worker báo qua heartbeat, chỉ trong RAM của API (F06 R4, R9)."""

    fps: float | None
    brightness: float | None
    dropped_frames: int | None
    source_status: str | None
    updated_at: datetime


class CameraDetailOut(CameraOut):
    """`GET /cameras/{id}`: thêm `runtime` (null khi chưa có heartbeat từ lúc API khởi động)."""

    runtime: CameraRuntimeOut | None = None
    # Bed ROI chuẩn hóa 0–1 để màn hình "Theo dõi trực tiếp" vẽ đè (F07 R6); null = chưa cấu hình.
    roi_polygon: list[list[float]] | None = None


class CameraRoiIn(StrictIn):
    """`PUT /cameras/{id}/roi` (F08 R1). Điểm kiểm tra bằng `validate_roi_polygon` (lỗi 400
    `INVALID_ROI_POLYGON`), nên ở đây chỉ cần là danh sách."""

    roi_polygon: list[Any]


class CameraDisplayModeIn(StrictIn):
    """`PUT /cameras/{id}/display-mode` (F28 R2). Giá trị ngoài `RAW`/`BLUR`/`SKELETON` → 422."""

    display_mode: DisplayMode


class CameraRoiOut(BaseModel):
    camera_id: int
    roi_polygon: list[list[float]]
    config_version: int


class CameraThresholdsIn(StrictIn):
    """`PUT /cameras/{id}/thresholds` (F08 R4): thay toàn bộ override; `{}` = khôi phục mặc định.

    Lồng nhau như `config/engine.default.yaml`, ví dụ `{"posture": {"lying_enter_deg": 20}}`.
    """

    thresholds: dict[str, Any]


class ThresholdLimit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    min: float | None = None
    max: float | None = None


class ThresholdRelation(BaseModel):
    """`low` ≤ `high` (strict: `low` < `high`) trên giá trị đang áp dụng."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    low: str
    high: str
    strict: bool = False


class ThresholdRules(BaseModel):
    """Quy tắc override theo camera (`config/camera_overrides.yaml`; F08 R4, AGENTS.md quy tắc 6).

    `allowed`, khóa của `limits`: đường dẫn `a.b` hoặc mẫu `a.*` (fnmatch).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: list[str]
    limits: dict[str, ThresholdLimit] = Field(default_factory=dict)
    relations: list[ThresholdRelation] = Field(default_factory=list)

    def is_allowed(self, path: str) -> bool:
        return any(fnmatchcase(path, pattern) for pattern in self.allowed)

    def limit_for(self, path: str) -> ThresholdLimit | None:
        for pattern, limit in self.limits.items():
            if fnmatchcase(path, pattern):
                return limit
        return None


class CameraThresholdsOut(BaseModel):
    """Ngưỡng mặc định, override của camera, giá trị đang áp dụng và quy tắc override."""

    defaults: dict[str, Any]
    overrides: dict[str, Any]
    effective: dict[str, Any]
    config_version: int
    rules: ThresholdRules


# Mã và chuỗi bắt buộc: bỏ khoảng trắng đầu/cuối rồi mới kiểm tra (F03 R6).
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class BedCreate(StrictIn):
    code: Code
    area_id: int  # khu vực đang dùng (F37 R3)


class BedUpdate(StrictIn):
    """Chỉ trường gửi lên mới đổi. Không có `is_active`: xóa/khôi phục qua DELETE, restore."""

    code: Code | None = None
    area_id: int | None = None


class AreaCreate(StrictIn):
    code: Code
    name: Label


class AreaUpdate(StrictIn):
    code: Code | None = None
    name: Label | None = None


class ShiftCreate(StrictIn):
    """Giờ `HH:mm` (giây = 0) và `start_time ≠ end_time` kiểm tra ở domain để trả 400 (R8)."""

    name: Label
    start_time: time
    end_time: time


class ShiftUpdate(StrictIn):
    name: Label | None = None
    start_time: time | None = None
    end_time: time | None = None


class PatientCreate(StrictIn):
    """Chỉ mã thử nghiệm và ghi chú; `full_name`, `photo`… bị từ chối (PDF §10.1; HS §6.3)."""

    code: Code
    note: Note | None = None


class PatientUpdate(StrictIn):
    code: Code | None = None
    note: Note | None = None


class CameraCreate(StrictIn):
    name: Label
    source_type: CameraSourceType
    # Kiểm tra theo `source_type` ở domain (F03 R5) để trả 400 kèm `details.field`.
    source: Annotated[str, StringConstraints(max_length=1000)]
    bed_id: int | None = None


class CameraUpdate(StrictIn):
    """`bed_id: null` nghĩa là gỡ camera khỏi giường; không gửi thì giữ nguyên."""

    name: Label | None = None
    source_type: CameraSourceType | None = None
    source: Annotated[str, StringConstraints(max_length=1000)] | None = None
    bed_id: int | None = None


def session_out(s: MonitoringSession) -> SessionOut:
    return SessionOut(
        id=s.id,
        bed_id=s.bed_id,
        bed_code=s.bed.code,
        patient_id=s.patient_id,
        patient_code=s.patient.code,
        camera_id=s.camera_id,
        started_at=s.started_at,
        started_by=UserRef(id=s.starter.id, full_name=s.starter.full_name),
        ended_at=s.ended_at,
        ended_by=user_ref(s.ender),
        previous_session_id=s.previous_session_id,
        previous_bed_code=s.previous_session.bed.code if s.previous_session else None,
        next_session_id=s.next_session.id if s.next_session else None,
        transfer_reason=s.transfer_reason,
        paused_at=s.paused_at,
        paused_by=user_ref(s.pauser),
    )


def camera_ref(c: Camera | None) -> CameraRef | None:
    return CameraRef(id=c.id, name=c.name, status=c.status) if c else None


def area_ref(a: Area) -> AreaRef:
    return AreaRef(id=a.id, code=a.code, name=a.name)


def area_out(a: Area, bed_count: int) -> AreaOut:
    return AreaOut(
        id=a.id,
        code=a.code,
        name=a.name,
        is_active=a.is_active,
        created_at=a.created_at,
        bed_count=bed_count,
    )


def bed_out(b: Bed, active: MonitoringSession | None) -> BedOut:
    return BedOut(
        id=b.id,
        code=b.code,
        area=area_ref(b.area),
        is_active=b.is_active,
        camera=camera_ref(b.camera),
        active_session=session_out(active) if active else None,
    )


def patient_out(p: Patient, active_session_id: int | None) -> PatientOut:
    return PatientOut(
        id=p.id,
        code=p.code,
        note=p.note,
        is_active=p.is_active,
        active_session_id=active_session_id,
    )


def camera_out(c: Camera) -> CameraOut:
    return CameraOut(
        id=c.id,
        name=c.name,
        bed_id=c.bed_id,
        bed_code=c.bed.code if c.bed else None,
        source_type=c.source_type,
        source=c.source,
        display_mode=c.display_mode,
        status=c.status,
        last_seen_at=c.last_seen_at,
        config_version=c.config_version,
        is_active=c.is_active,
    )


# ---------- Trạng thái giường (RAM) ----------


class FaceSignalsIn(BaseModel):
    eyes_closed: bool = False
    eyes_closed_prolonged: bool = False
    brow_down: bool = False
    eye_squint: bool = False
    nose_sneer: bool = False
    mouth_change: bool = False


class BedStateIn(StrictIn):
    body_state: BodyState
    observation_quality: ObservationQuality
    activity_level: ActivityLevel = ActivityLevel.UNKNOWN
    rest_status: RestStatus = RestStatus.UNKNOWN
    face_status: FaceStatus = FaceStatus.NOT_VISIBLE
    face_signals: FaceSignalsIn = Field(default_factory=FaceSignalsIn)
    ts: AwareDatetime | None = None


class BedStateOut(BaseModel):
    bed_id: int
    body_state: BodyState
    observation_quality: ObservationQuality
    activity_level: ActivityLevel
    rest_status: RestStatus
    face_status: FaceStatus
    face_signals: FaceSignalsIn
    updated_at: datetime


class CameraStatusOut(BaseModel):
    camera_id: int
    bed_id: int | None
    status: CameraStatus
    fps: float | None
    brightness: float | None


# ---------- Sự kiện và cảnh báo ----------


class EventOut(BaseModel):
    id: int
    event_uid: str
    session_id: int | None
    bed_id: int | None
    bed_code: str | None
    camera_id: int
    code: EventCode
    priority: Priority
    occurred_at: AwareDatetime
    detected_at: AwareDatetime
    created_at: datetime
    confidence: float
    observation_quality: ObservationQuality
    explanation: dict[str, Any]
    alert_id: int | None
    alert_status: AlertStatus | None


class EventIn(StrictIn):
    event_uid: str = Field(min_length=8, max_length=36)
    camera_id: int
    code: EventCode
    priority: Priority
    occurred_at: AwareDatetime
    detected_at: AwareDatetime
    confidence: float = Field(ge=0, le=1)
    observation_quality: ObservationQuality
    explanation: dict[str, Any] = Field(default_factory=dict)
    config_hash: str = ""


class EventIngestOut(BaseModel):
    id: int
    created: bool


class AlertEventRef(BaseModel):
    id: int
    code: EventCode
    priority: Priority
    occurred_at: AwareDatetime
    observation_quality: ObservationQuality


class BedRef(BaseModel):
    id: int
    code: str


class SessionRef(BaseModel):
    id: int
    patient_code: str


class AlertOut(BaseModel):
    id: int
    status: AlertStatus
    outcome: AlertOutcome | None
    note: str | None
    created_at: datetime
    acknowledged_by: UserRef | None
    acknowledged_at: datetime | None
    outcome_by: UserRef | None
    outcome_at: datetime | None
    resolved_by: UserRef | None
    resolved_at: datetime | None
    event: AlertEventRef
    bed: BedRef | None
    session: SessionRef | None


class AlertCreatedOut(BaseModel):
    alert: AlertOut
    event: EventOut


class OutcomeIn(StrictIn):
    outcome: AlertOutcome
    note: str | None = Field(default=None, max_length=1000)


class ResolveIn(StrictIn):
    note: str | None = Field(default=None, max_length=1000)


def event_out(e: Event) -> EventOut:
    return EventOut(
        id=e.id,
        event_uid=e.event_uid,
        session_id=e.session_id,
        bed_id=e.bed_id,
        bed_code=e.bed.code if e.bed else None,
        camera_id=e.camera_id,
        code=e.code,
        priority=e.priority,
        occurred_at=e.occurred_at,
        detected_at=e.detected_at,
        created_at=e.created_at,
        confidence=e.confidence,
        observation_quality=e.observation_quality,
        explanation=e.explanation or {},
        alert_id=e.alert.id if e.alert else None,
        alert_status=e.alert.status if e.alert else None,
    )


def alert_out(a: Alert) -> AlertOut:
    e = a.event
    return AlertOut(
        id=a.id,
        status=a.status,
        outcome=a.outcome,
        note=a.note,
        created_at=a.created_at,
        acknowledged_by=user_ref(a.acknowledger),
        acknowledged_at=a.acknowledged_at,
        outcome_by=user_ref(a.outcome_user),
        outcome_at=a.outcome_at,
        resolved_by=user_ref(a.resolver),
        resolved_at=a.resolved_at,
        event=AlertEventRef(
            id=e.id,
            code=e.code,
            priority=e.priority,
            occurred_at=e.occurred_at,
            observation_quality=e.observation_quality,
        ),
        bed=BedRef(id=e.bed.id, code=e.bed.code) if e.bed else None,
        session=SessionRef(id=e.session.id, patient_code=e.session.patient.code)
        if e.session
        else None,
    )


# ---------- Tổng quan ----------


class OverviewSessionOut(BaseModel):
    id: int
    patient_code: str
    started_at: datetime
    paused_at: datetime | None  # F09: null = không tạm dừng thu hình (F04 R19)


class OverviewBedOut(BaseModel):
    bed_id: int
    code: str
    area: str  # tên khu vực (F37: giữ dạng chuỗi cho F09)
    session: OverviewSessionOut | None
    camera: CameraRef | None
    pending_alert_count: int
    acknowledged_alert_count: int
    max_open_priority: Priority | None
    state: BedStateOut | None


class OverviewOut(BaseModel):
    current_shift: ShiftOut | None
    beds: list[OverviewBedOut]


# ---------- Timeline ----------


class TimelineAlertRef(BaseModel):
    id: int
    status: AlertStatus
    outcome: AlertOutcome | None
    acknowledged_by: UserRef | None


class TimelineItemOut(BaseModel):
    kind: Literal["event", "alert_action"]
    time: datetime
    bed_code: str | None
    event_id: int
    code: EventCode
    priority: Priority
    observation_quality: ObservationQuality | None = None
    alert: TimelineAlertRef | None = None
    action: Literal["alert.acknowledge", "alert.outcome", "alert.resolve"] | None = None
    actor: UserRef | None = None
    outcome: AlertOutcome | None = None
    note: str | None = None
    alert_id: int | None = None


# ---------- Bàn giao ca ----------


class HandoverBedOut(BaseModel):
    bed_id: int
    code: str
    event_counts: dict[EventCode, int]
    alerts_resolved: int
    alerts_unresolved: int
    state_change_count: int


class HandoverOut(BaseModel):
    from_: datetime = Field(serialization_alias="from")
    to: datetime
    shift: ShiftOut | None
    beds: list[HandoverBedOut]
    outstanding_alerts: list[AlertOut]

    model_config = ConfigDict(populate_by_name=True)


# ---------- API nội bộ ----------


class HeartbeatIn(StrictIn):
    fps: float | None = None
    brightness: float | None = None
    dropped_frames: int | None = None
    source_status: str | None = None


class HeartbeatOut(BaseModel):
    config_version: int


class CameraConfigOut(BaseModel):
    camera_id: int
    bed_id: int | None
    source_type: CameraSourceType
    source: str
    roi_polygon: list[list[float]] | None
    thresholds: dict[str, Any]
    display_mode: DisplayMode
    config_version: int
    active_session_id: int | None
    # Phiên đang mở của giường đang tạm dừng thu hình: worker dừng đọc khung (F04 R22; F36 R18).
    capture_paused: bool = False
