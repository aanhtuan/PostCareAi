"""Quyền xem của người nhà theo phiên (F36; QA#31; MS §3).

- Hiệu lực tính lúc truy vấn (R5) bằng `now` do lớp API truyền vào (đồng hồ inject được).
- Mọi thao tác ghi: audit trong cùng transaction, commit, rồi mới báo realtime (AGENTS.md quy
  tắc 7). Thu hồi phát message nội bộ `family.grant_ended`; hub chiếu thành `family.access_ended`.
- Người nhà không bao giờ nhận mã bệnh nhân, tên nhân viên, `note`, `explanation`, tín hiệu
  khuôn mặt hay ảnh (R8–R11).
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from postcare.db.models import Camera, FamilyAccessGrant, MonitoringSession, User
from postcare.domain.audit import record_audit
from postcare.domain.dto import (
    FamilyAccountOut,
    FamilyGrantCreate,
    FamilyGrantOut,
    FamilyGrantSummaryOut,
    FamilySkeletonOut,
    FamilyStateOut,
    FamilyTimelineItemOut,
    FamilyViewOut,
    Page,
    UserRef,
    user_ref,
)
from postcare.domain.errors import DomainError, not_found, validation_error
from postcare.domain.notifications import Publisher, safe_publish
from postcare.domain.runtime import RuntimeStore
from postcare.domain.timeline import family_session_timeline
from postcare.schemas.enums import FamilyAccessEndReason, ShareLevel, UserRole

ENTITY = "family_access_grant"
GRANT_ENDED = "family.grant_ended"  # message nội bộ cho hub, không gửi cho client


def grant_end_reason(grant: FamilyAccessGrant, now: datetime) -> FamilyAccessEndReason | None:
    """`None` khi quyền còn hiệu lực (R5); nếu không, lý do hết hiệu lực."""
    if grant.revoked_at is not None:
        return FamilyAccessEndReason.REVOKED
    if grant.session.ended_at is not None:
        return FamilyAccessEndReason.SESSION_ENDED
    if not grant.user.is_active or grant.user.role is not UserRole.FAMILY:
        return FamilyAccessEndReason.ACCOUNT_LOCKED
    if grant.expires_at is not None and grant.expires_at <= now:
        return FamilyAccessEndReason.EXPIRED
    return None


def is_grant_active(grant: FamilyAccessGrant, now: datetime) -> bool:
    return grant_end_reason(grant, now) is None


def _grant_out(g: FamilyAccessGrant, now: datetime) -> FamilyGrantOut:
    reason = grant_end_reason(g, now)
    return FamilyGrantOut(
        id=g.id,
        session_id=g.session_id,
        bed_code=g.session.bed.code,
        user=UserRef(id=g.user.id, full_name=g.user.full_name),
        share_level=g.share_level,
        consent_note=g.consent_note,
        granted_by=UserRef(id=g.granter.id, full_name=g.granter.full_name),
        granted_at=g.granted_at,
        expires_at=g.expires_at,
        revoked_at=g.revoked_at,
        revoked_by=user_ref(g.revoker),
        active=reason is None,
        end_reason=reason,
    )


def _forbidden() -> DomainError:
    return DomainError("FORBIDDEN", "Không đủ quyền thực hiện thao tác này", 403)


# ---------- Nhân viên: cấp, liệt kê, thu hồi ----------


def list_family_accounts(db: Session) -> Page[FamilyAccountOut]:
    users = db.scalars(
        select(User)
        .where(User.role == UserRole.FAMILY, User.is_active.is_(True))
        .order_by(User.username)
    ).all()
    items = [FamilyAccountOut(id=u.id, username=u.username, full_name=u.full_name) for u in users]
    return Page[FamilyAccountOut](items=items, total=len(items))


def grant_access(
    db: Session, *, session_id: int, data: FamilyGrantCreate, actor: User, now: datetime
) -> FamilyGrantOut:
    # Khóa hàng phiên: không tranh chấp với kết thúc phiên / chuyển giường (F04).
    session = db.get(MonitoringSession, session_id, with_for_update=True, populate_existing=True)
    if session is None:
        raise not_found("Không tìm thấy phiên theo dõi")
    if session.ended_at is not None:
        raise DomainError("SESSION_ALREADY_ENDED", "Phiên theo dõi đã kết thúc", 409)
    note = data.consent_note.strip()
    if not note:
        raise validation_error("Cần ghi chú chấp thuận chia sẻ", {"field": "consent_note"})
    user = db.get(User, data.user_id)
    if user is None or user.role is not UserRole.FAMILY or not user.is_active:
        raise validation_error(
            "Tài khoản nhận quyền phải là người nhà đang dùng", {"field": "user_id"}
        )
    if data.expires_at is not None and data.expires_at <= now:
        raise validation_error("Thời điểm hết hạn phải ở tương lai", {"field": "expires_at"})

    existing = db.scalar(
        select(FamilyAccessGrant)
        .where(
            FamilyAccessGrant.session_id == session_id,
            FamilyAccessGrant.user_id == user.id,
            FamilyAccessGrant.revoked_at.is_(None),
        )
        .with_for_update()
    )
    if existing is not None:
        if is_grant_active(existing, now):
            raise DomainError(
                "FAMILY_GRANT_ALREADY_ACTIVE",
                "Người nhà này đã có quyền xem phiên theo dõi",
                409,
                {"grant_id": existing.id},
            )
        # Quyền cũ đã hết hạn nhưng chưa thu hồi: hệ thống đóng lại để cấp mới (giả định F36 §9).
        existing.revoked_at = now
        record_audit(
            db,
            actor_user_id=None,
            action="family_access.revoke",
            entity_type=ENTITY,
            entity_id=existing.id,
            before={"revoked_at": None},
            after={"revoked_at": now, "reason": FamilyAccessEndReason.EXPIRED.value},
        )
        db.flush()

    grant = FamilyAccessGrant(
        session_id=session_id,
        user_id=user.id,
        share_level=data.share_level,
        consent_note=note,
        granted_by=actor.id,
        granted_at=now,
        expires_at=data.expires_at,
    )
    db.add(grant)
    try:
        db.flush()
    except IntegrityError as exc:  # hai yêu cầu đồng thời: partial unique index chặn
        db.rollback()
        raise DomainError(
            "FAMILY_GRANT_ALREADY_ACTIVE", "Người nhà này đã có quyền xem phiên theo dõi", 409
        ) from exc
    record_audit(
        db,
        actor_user_id=actor.id,
        action="family_access.grant",
        entity_type=ENTITY,
        entity_id=grant.id,
        after={
            "session_id": session_id,
            "user_id": user.id,
            "share_level": grant.share_level,
            "consent_note": note,
            "expires_at": grant.expires_at,
        },
    )
    db.commit()
    db.refresh(grant)
    return _grant_out(grant, now)


def revoke_access(
    db: Session,
    *,
    grant_id: int,
    reason: str | None,
    actor: User,
    now: datetime,
    publisher: Publisher,
) -> FamilyGrantOut:
    grant = db.get(FamilyAccessGrant, grant_id, with_for_update=True, populate_existing=True)
    if grant is None:
        raise not_found("Không tìm thấy quyền xem")
    if not is_grant_active(grant, now):
        raise DomainError("FAMILY_GRANT_NOT_ACTIVE", "Quyền xem đã hết hiệu lực", 409)
    grant.revoked_at = now
    grant.revoked_by = actor.id
    record_audit(
        db,
        actor_user_id=actor.id,
        action="family_access.revoke",
        entity_type=ENTITY,
        entity_id=grant.id,
        before={"revoked_at": None},
        after={"revoked_at": now, "reason": (reason or "").strip() or None},
    )
    db.commit()
    db.refresh(grant)
    safe_publish(
        publisher,
        GRANT_ENDED,
        {
            "grant_id": grant.id,
            "user_id": grant.user_id,
            "reason": FamilyAccessEndReason.REVOKED.value,
        },
    )
    return _grant_out(grant, now)


def list_session_grants(db: Session, session_id: int, now: datetime) -> Page[FamilyGrantOut]:
    if db.get(MonitoringSession, session_id) is None:
        raise not_found("Không tìm thấy phiên theo dõi")
    grants = db.scalars(
        select(FamilyAccessGrant)
        .where(FamilyAccessGrant.session_id == session_id)
        .order_by(FamilyAccessGrant.granted_at.desc(), FamilyAccessGrant.id.desc())
    ).all()
    items = [_grant_out(g, now) for g in grants]
    return Page[FamilyGrantOut](items=items, total=len(items))


def session_shares_skeleton(db: Session, session_id: int, now: datetime) -> bool:
    """Phiên có quyền mức SKELETON đang hiệu lực: worker mới gửi keypoint (R11)."""
    grants = db.scalars(
        select(FamilyAccessGrant).where(
            FamilyAccessGrant.session_id == session_id,
            FamilyAccessGrant.revoked_at.is_(None),
            FamilyAccessGrant.share_level == ShareLevel.SKELETON,
        )
    )
    return any(is_grant_active(g, now) for g in grants)


# ---------- Người nhà ----------


def active_grants_for_user(db: Session, user: User, now: datetime) -> list[FamilyAccessGrant]:
    grants = db.scalars(
        select(FamilyAccessGrant)
        .join(MonitoringSession, MonitoringSession.id == FamilyAccessGrant.session_id)
        .where(
            FamilyAccessGrant.user_id == user.id,
            FamilyAccessGrant.revoked_at.is_(None),
            MonitoringSession.ended_at.is_(None),
        )
        .options(selectinload(FamilyAccessGrant.session).selectinload(MonitoringSession.bed))
        .order_by(FamilyAccessGrant.id)
    ).all()
    return [g for g in grants if is_grant_active(g, now)]


def _own_active_grant(db: Session, user: User, grant_id: int, now: datetime) -> FamilyAccessGrant:
    """Grant của người khác hoặc không tồn tại → 403 FORBIDDEN (không lộ sự tồn tại); của chính
    mình nhưng hết hiệu lực → 403 FAMILY_ACCESS_ENDED (R7)."""
    grant = db.get(FamilyAccessGrant, grant_id)
    if grant is None or grant.user_id != user.id:
        raise _forbidden()
    reason = grant_end_reason(grant, now)
    if reason is not None:
        raise DomainError(
            "FAMILY_ACCESS_ENDED", "Quyền xem đã kết thúc", 403, {"reason": reason.value}
        )
    return grant


def record_view(db: Session, user: User, grant: FamilyAccessGrant, channel: str) -> None:
    """Audit `family_access.view` (R6): mỗi request `view` và mỗi lần mở WebSocket."""
    record_audit(
        db,
        actor_user_id=user.id,
        action="family_access.view",
        entity_type=ENTITY,
        entity_id=grant.id,
        after={"channel": channel},
    )


def grant_summary(g: FamilyAccessGrant) -> FamilyGrantSummaryOut:
    return FamilyGrantSummaryOut(
        id=g.id,
        bed_code=g.session.bed.code,
        session_started_at=g.session.started_at,
        share_level=g.share_level,
        expires_at=g.expires_at,
        capture_paused=g.session.paused_at is not None,
    )


def my_grants(db: Session, user: User, now: datetime) -> Page[FamilyGrantSummaryOut]:
    items = [grant_summary(g) for g in active_grants_for_user(db, user, now)]
    return Page[FamilyGrantSummaryOut](items=items, total=len(items))


def family_state(
    grant: FamilyAccessGrant, store: RuntimeStore, capture_paused: bool
) -> FamilyStateOut | None:
    """Trạng thái hiện tại đã lọc (R9). Trạng thái có từ trước khi phiên bắt đầu không hiện."""
    state = store.get_bed_state(grant.session.bed_id)
    if state is None or state.updated_at < grant.session.started_at:
        return None
    return FamilyStateOut(
        body_state=state.body_state,
        observation_quality=state.observation_quality,
        activity_level=state.activity_level,
        rest_status=state.rest_status,
        capture_paused=capture_paused,
        updated_at=state.updated_at,
    )


def session_roi(db: Session, session: MonitoringSession) -> list[list[float]] | None:
    camera = db.get(Camera, session.camera_id) if session.camera_id else None
    return camera.roi_polygon if camera else None


def family_view(
    db: Session, *, user: User, grant_id: int, store: RuntimeStore, now: datetime
) -> FamilyViewOut:
    grant = _own_active_grant(db, user, grant_id, now)
    session = grant.session
    paused = session.paused_at is not None
    skeleton = None
    if grant.share_level is ShareLevel.SKELETON:
        sk = store.get_skeleton(session.bed_id)
        fresh = sk is not None and sk.ts >= session.started_at
        skeleton = FamilySkeletonOut(
            keypoints=sk.keypoints if fresh and sk and not paused else None,
            roi_polygon=session_roi(db, session),
            ts=sk.ts if fresh and sk else None,
        )
    out = FamilyViewOut(
        grant_id=grant.id,
        bed_code=session.bed.code,
        session_started_at=session.started_at,
        share_level=grant.share_level,
        capture_paused=paused,
        state=family_state(grant, store, paused),
        skeleton=skeleton,
    )
    record_view(db, user, grant, "rest")
    db.commit()
    return out


def family_timeline(
    db: Session, *, user: User, grant_id: int, limit: int, offset: int, now: datetime
) -> Page[FamilyTimelineItemOut]:
    grant = _own_active_grant(db, user, grant_id, now)
    page = family_session_timeline(db, grant.session_id, limit, offset)
    items: list[FamilyTimelineItemOut] = []
    for it in page.items:
        if it.kind == "event":
            items.append(
                FamilyTimelineItemOut(
                    time=it.time,
                    kind="event",
                    event_id=it.event_id,
                    code=it.code,
                    priority=it.priority,
                    alert_status=it.alert.status if it.alert else None,
                )
            )
        else:
            kind = "capture_paused" if it.action == "session.pause" else "capture_resumed"
            items.append(
                FamilyTimelineItemOut(
                    time=it.time,
                    kind=kind,
                    event_id=None,
                    code=None,
                    priority=None,
                    alert_status=None,
                )
            )
    return Page[FamilyTimelineItemOut](items=items, total=page.total)
