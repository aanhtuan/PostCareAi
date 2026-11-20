"""Camera phía worker: cấu hình, heartbeat, trạng thái giường, phát hiện mất kết nối (A02)."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import Bed, Camera
from postcare.db.types import utcnow
from postcare.domain.dto import (
    BedStateIn,
    BedStateOut,
    CameraConfigOut,
    CameraStatusOut,
    FaceSignalsIn,
    HeartbeatIn,
    HeartbeatOut,
)
from postcare.domain.errors import not_found, validation_error
from postcare.domain.events import create_camera_event, publish_created
from postcare.domain.notifications import Publisher, safe_publish
from postcare.domain.runtime import CameraRuntime, RuntimeStore
from postcare.domain.sessions import session_at
from postcare.schemas.enums import (
    ActivityLevel,
    BodyState,
    CameraStatus,
    FaceStatus,
    ObservationQuality,
    RestStatus,
)
from postcare.schemas.events import EventCode


def worker_camera_ids(db: Session) -> list[int]:
    """F31 R4: camera cần worker = camera đang dùng, gắn với giường đang dùng (theo id)."""
    return list(
        db.scalars(
            select(Camera.id)
            .join(Bed, Camera.bed_id == Bed.id)
            .where(Camera.is_active.is_(True), Bed.is_active.is_(True))
            .order_by(Camera.id)
        )
    )


def _camera(db: Session, camera_id: int) -> Camera:
    camera = db.get(Camera, camera_id)
    if camera is None or not camera.is_active:
        raise not_found("Không tìm thấy camera")
    return camera


def worker_camera_config_version(db: Session, camera_id: int) -> int:
    """Phiên bản cấu hình của camera đang dùng, hoặc 404 (F06 R2, R8)."""
    return _camera(db, camera_id).config_version


def camera_config(db: Session, camera_id: int) -> CameraConfigOut:
    camera = _camera(db, camera_id)
    session = session_at(db, camera.bed_id, utcnow()) if camera.bed_id else None
    return CameraConfigOut(
        camera_id=camera.id,
        bed_id=camera.bed_id,
        source_type=camera.source_type,
        source=camera.source,
        roi_polygon=camera.roi_polygon,
        thresholds=camera.thresholds or {},
        display_mode=camera.display_mode,
        observation_profile=camera.observation_profile,
        config_version=camera.config_version,
        active_session_id=session.id if session else None,
        capture_paused=session is not None and session.paused_at is not None,
    )


def _status_out(camera: Camera, runtime: CameraRuntime) -> CameraStatusOut:
    return CameraStatusOut(
        camera_id=camera.id,
        bed_id=camera.bed_id,
        status=camera.status,
        fps=runtime.fps,
        brightness=runtime.brightness,
    )


# Worker còn sống nhưng không đọc nguồn có chủ đích (tạm dừng thu hình, F36 R18): vẫn ONLINE.
_SOURCE_STATUSES_ONLINE = {CameraStatus.ONLINE.value, "PAUSED"}


def _camera_status_from(source_status: str | None) -> CameraStatus:
    """F06 R4: nguồn ONLINE (hoặc PAUSED) → ONLINE; nguồn khác (OFFLINE, UNKNOWN…) → OFFLINE.

    Không gửi `source_status` (client cũ, giả lập) coi như ONLINE *(giả định)*.
    """
    if source_status is None or source_status.upper() in _SOURCE_STATUSES_ONLINE:
        return CameraStatus.ONLINE
    return CameraStatus.OFFLINE


def heartbeat(
    db: Session, camera_id: int, data: HeartbeatIn, store: RuntimeStore, publisher: Publisher
) -> HeartbeatOut:
    camera = _camera(db, camera_id)
    now = utcnow()
    previous = camera.status
    new_status = _camera_status_from(data.source_status)
    runtime = CameraRuntime(
        data.fps, data.brightness, data.dropped_frames, data.source_status, updated_at=now
    )
    store.set_camera(camera.id, runtime)
    if new_status is CameraStatus.OFFLINE:
        camera.last_seen_at = now
        if previous == CameraStatus.ONLINE:
            # Worker còn sống nhưng mất nguồn video: cùng đường với mất heartbeat (F17 R17).
            _go_offline(db, camera, store, publisher, runtime, reason="source_offline", now=now)
        else:
            camera.status = CameraStatus.OFFLINE
            db.commit()
        return HeartbeatOut(config_version=camera.config_version)
    camera.last_seen_at = now
    camera.status = CameraStatus.ONLINE
    created = None
    if previous == CameraStatus.OFFLINE:
        created = create_camera_event(
            db, camera, code=EventCode.CAMERA_ONLINE, occurred_at=now, reason="heartbeat"
        )
    db.commit()
    if previous != CameraStatus.ONLINE:
        safe_publish(publisher, "camera.status", _status_out(camera, runtime))
    if created:
        publish_created(db, publisher, *created)
    return HeartbeatOut(config_version=camera.config_version)


def update_bed_state(
    db: Session, camera_id: int, data: BedStateIn, store: RuntimeStore, publisher: Publisher
) -> BedStateOut:
    """Trạng thái giường chỉ nằm trong RAM; không có gì để commit nên phát ngay (F18 R4)."""
    camera = _camera(db, camera_id)
    if camera.bed_id is None:
        raise validation_error("Camera chưa gắn giường")
    state = BedStateOut(
        bed_id=camera.bed_id,
        body_state=data.body_state,
        observation_quality=data.observation_quality,
        activity_level=data.activity_level,
        rest_status=data.rest_status,
        face_status=data.face_status,
        face_signals=data.face_signals,
        updated_at=data.ts or utcnow(),
    )
    store.set_bed_state(state)
    safe_publish(publisher, "bed.state", state)
    return state


def mark_offline_cameras(
    db: Session,
    store: RuntimeStore,
    publisher: Publisher,
    *,
    offline_after_s: float,
    now: datetime | None = None,
) -> list[int]:
    """Camera ONLINE quá `offline_after_s` không có heartbeat → OFFLINE + CAMERA_OFFLINE."""
    now = now or utcnow()
    limit = now - timedelta(seconds=offline_after_s)
    cameras = list(
        db.scalars(
            select(Camera).where(
                Camera.status == CameraStatus.ONLINE,
                Camera.last_seen_at.is_not(None),
                Camera.last_seen_at < limit,
            )
        )
    )
    changed: list[int] = []
    for camera in cameras:
        assert camera.last_seen_at is not None
        _go_offline(
            db,
            camera,
            store,
            publisher,
            CameraRuntime(),
            reason="heartbeat_timeout",
            now=now,
            occurred_at=camera.last_seen_at,
        )
        changed.append(camera.id)
    return changed


def _go_offline(
    db: Session,
    camera: Camera,
    store: RuntimeStore,
    publisher: Publisher,
    runtime: CameraRuntime,
    *,
    reason: str,
    now: datetime,
    occurred_at: datetime | None = None,
) -> None:
    """ONLINE → OFFLINE: commit + CAMERA_OFFLINE, rồi phát camera.status, sự kiện, bed.state."""
    camera.status = CameraStatus.OFFLINE
    created = create_camera_event(
        db,
        camera,
        code=EventCode.CAMERA_OFFLINE,
        occurred_at=occurred_at or now,
        reason=reason,
    )
    db.commit()
    safe_publish(publisher, "camera.status", _status_out(camera, runtime))
    if created:
        publish_created(db, publisher, *created)
    if camera.bed_id is not None:
        # Mất camera: không còn quan sát được, không coi là "an toàn" (PRD US07).
        state = BedStateOut(
            bed_id=camera.bed_id,
            body_state=BodyState.NO_OBSERVATION,
            observation_quality=ObservationQuality.CAMERA_ISSUE,
            activity_level=ActivityLevel.UNKNOWN,
            rest_status=RestStatus.UNKNOWN,
            face_status=FaceStatus.NOT_VISIBLE,
            face_signals=FaceSignalsIn(),
            updated_at=now,
        )
        store.set_bed_state(state)
        safe_publish(publisher, "bed.state", state)
