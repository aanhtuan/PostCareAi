"""Enum dùng chung giữa DB, API và giả lập. Giá trị IN HOA khớp tài liệu kiến trúc."""

from enum import StrEnum


class UserRole(StrEnum):
    NURSE = "NURSE"
    CHARGE_NURSE = "CHARGE_NURSE"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"
    FAMILY = "FAMILY"  # QA#31: người nhà; bị chặn mặc định ở API nhân viên (F35), F36 mở phần riêng


# Vai trò nhân viên (api-conventions.md; F35 R2). FAMILY không thuộc nhóm này.
STAFF_ROLES: tuple[UserRole, ...] = (
    UserRole.NURSE,
    UserRole.CHARGE_NURSE,
    UserRole.DOCTOR,
    UserRole.ADMIN,
)


class BodyState(StrEnum):
    LYING = "LYING"
    RAISING = "RAISING"
    SITTING = "SITTING"
    AT_EDGE = "AT_EDGE"
    STANDING = "STANDING"
    OUT_OF_BED = "OUT_OF_BED"
    NO_OBSERVATION = "NO_OBSERVATION"


class ObservationQuality(StrEnum):
    GOOD = "GOOD"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    MULTIPLE_PEOPLE = "MULTIPLE_PEOPLE"
    NO_PERSON = "NO_PERSON"
    CAMERA_ISSUE = "CAMERA_ISSUE"


class ActivityLevel(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class RestStatus(StrEnum):
    RESTING = "RESTING"
    ACTIVE = "ACTIVE"
    UNKNOWN = "UNKNOWN"


class FaceStatus(StrEnum):
    OK = "OK"
    NOT_VISIBLE = "NOT_VISIBLE"
    TOO_SMALL = "TOO_SMALL"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class Priority(StrEnum):
    LOG = "LOG"
    INFO = "INFO"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


PRIORITY_RANK: dict[Priority, int] = {
    Priority.LOG: 0,
    Priority.INFO: 1,
    Priority.MEDIUM: 2,
    Priority.HIGH: 3,
}


class AlertStatus(StrEnum):
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AlertOutcome(StrEnum):
    CONFIRMED = "CONFIRMED"
    FALSE_ALARM = "FALSE_ALARM"
    PATIENT_SAFE = "PATIENT_SAFE"


class CameraSourceType(StrEnum):
    WEBCAM = "WEBCAM"
    URL = "URL"
    FILE = "FILE"


class CameraStatus(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class DisplayMode(StrEnum):
    RAW = "RAW"
    BLUR = "BLUR"
    SKELETON = "SKELETON"


class ShareLevel(StrEnum):
    """Mức chia sẻ với người nhà (F36; MS §3). Không mức nào gửi ảnh (QA#29)."""

    INFO = "INFO"
    SKELETON = "SKELETON"


class FamilyAccessEndReason(StrEnum):
    """Lý do quyền xem của người nhà hết hiệu lực (F36 R5, R13)."""

    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    SESSION_ENDED = "SESSION_ENDED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
