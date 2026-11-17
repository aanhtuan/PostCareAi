"""Nhật ký thao tác: chỉ INSERT, không có hàm sửa/xóa (data-model.md audit_logs; PDF §10.1)."""

from collections.abc import Mapping
from datetime import UTC, date, datetime, time
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from postcare.db.models import AuditLog
from postcare.db.types import utcnow


def _jsonable(value: Any) -> Any:
    """Chuyển giá trị sang dạng lưu được trong jsonb. datetime → ISO 8601 UTC."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime trong audit phải có tzinfo")
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date | time):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    raise TypeError(f"Không chuyển được sang JSON cho audit: {type(value).__name__}")


def record_audit(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int,
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
) -> AuditLog:
    """Thêm một dòng audit vào session hiện tại. Không commit: người gọi commit cùng nghiệp vụ.

    `actor_user_id = None` nghĩa là hệ thống/worker.
    """
    log = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=None if before is None else _jsonable(before),
        after=None if after is None else _jsonable(after),
        created_at=utcnow(),
    )
    db.add(log)
    return log
