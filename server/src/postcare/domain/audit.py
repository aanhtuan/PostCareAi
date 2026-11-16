"""Nhật ký thao tác: chỉ INSERT, không có hàm sửa/xóa (data-model.md audit_logs)."""

from typing import Any

from sqlalchemy.orm import Session

from postcare.db.models import AuditLog
from postcare.db.types import utcnow


def record_audit(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    """Thêm một dòng audit trong transaction hiện tại (caller tự commit)."""
    log = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        created_at=utcnow(),
    )
    db.add(log)
    return log
