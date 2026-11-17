"""Danh mục giường, bệnh nhân (mã thử nghiệm), camera (F03).

- Thêm, sửa, xóa mềm (`is_active = false`), khôi phục; không có xóa cứng (QA#36).
- Mã (`code`) duy nhất kể cả bản ghi đã xóa (data-model.md "Quy ước").
- Mọi thao tác ghi có tác động gọi `record_audit()` trong cùng transaction (R10).
- Xóa/khôi phục lặp lại: trả bản ghi, không đổi gì, không audit (R16).
"""

import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from postcare.db.models import Bed, Camera, MonitoringSession, Patient, User
from postcare.domain.audit import record_audit
from postcare.domain.dto import (
    BedCreate,
    BedOut,
    BedUpdate,
    CameraCreate,
    CameraOut,
    CameraUpdate,
    Page,
    PatientCreate,
    PatientOut,
    PatientUpdate,
    bed_out,
    camera_out,
    patient_out,
)
from postcare.domain.errors import DomainError, not_found, validation_error
from postcare.schemas.enums import CameraSourceType

_URL_PREFIXES = ("http://", "https://", "rtsp://")
# Đổi các trường này thì worker phải tải lại cấu hình (R8; data-model.md cameras.config_version).
_CAMERA_CONFIG_FIELDS = ("source_type", "source", "bed_id")


# ---------- Dùng chung ----------


def _open_session(db: Session, **where: int) -> MonitoringSession | None:
    q = select(MonitoringSession).where(MonitoringSession.ended_at.is_(None))
    for column, value in where.items():
        q = q.where(getattr(MonitoringSession, column) == value)
    return db.scalar(q.limit(1))


def _active_sessions(db: Session) -> list[MonitoringSession]:
    return list(
        db.scalars(
            select(MonitoringSession)
            .where(MonitoringSession.ended_at.is_(None))
            .options(
                selectinload(MonitoringSession.patient),
                selectinload(MonitoringSession.bed),
                selectinload(MonitoringSession.starter),
            )
        )
    )


def _page[T](db: Session, q: Any, limit: int, offset: int, out: Any) -> Page[T]:
    total = db.scalar(select(func.count()).select_from(q.order_by(None).subquery())) or 0
    return Page(items=[out(x) for x in db.scalars(q.limit(limit).offset(offset))], total=total)


def _duplicate_code(label: str, code: str, existing: Bed | Patient) -> DomainError:
    if existing.is_active:
        message = f"{label} {code} đã tồn tại"
    else:
        message = f'{label} {code} thuộc một mục đã xóa. Dùng "Khôi phục" để dùng lại mục đó.'
    return DomainError(
        "DUPLICATE_CODE",
        message,
        409,
        {"field": "code", "existing_id": existing.id, "inactive": not existing.is_active},
    )


def _check_code(
    db: Session, model: type[Bed] | type[Patient], label: str, code: str, own_id: int | None
) -> None:
    existing = db.scalar(select(model).where(model.code == code))
    if existing is not None and existing.id != own_id:
        raise _duplicate_code(label, code, existing)


def _flush(db: Session, on_conflict: DomainError) -> None:
    """Hai yêu cầu đồng thời vượt qua kiểm tra trước: ràng buộc unique của DB chặn."""
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise on_conflict from exc


def _audit(
    db: Session,
    user: User,
    action: str,
    entity: Bed | Patient | Camera,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    entity_type = action.split(".", 1)[0]
    record_audit(
        db,
        actor_user_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity.id,
        before=before,
        after=after,
    )


def _locked[M: (Bed, Patient, Camera)](db: Session, model: type[M], entity_id: int, msg: str) -> M:
    """Khóa hàng tới hết transaction: kiểm tra phiên mở và xóa là một bước (R14)."""
    entity = db.get(model, entity_id, with_for_update=True)
    if entity is None:
        raise not_found(msg)
    return entity


# ---------- Giường ----------

_BED_LABEL = "Mã giường"
_BED_NOT_FOUND = "Không tìm thấy giường"


def _bed_snapshot(b: Bed) -> dict[str, Any]:
    return {"code": b.code, "area": b.area, "is_active": b.is_active}


def _bed_out(db: Session, b: Bed) -> BedOut:
    return bed_out(b, _open_session(db, bed_id=b.id))


def list_beds(
    db: Session, include_inactive: bool = False, limit: int = 50, offset: int = 0
) -> Page[BedOut]:
    q = select(Bed).options(selectinload(Bed.camera)).order_by(Bed.code)
    if not include_inactive:
        q = q.where(Bed.is_active.is_(True))
    by_bed = {s.bed_id: s for s in _active_sessions(db)}
    return _page(db, q, limit, offset, lambda b: bed_out(b, by_bed.get(b.id)))


def get_bed(db: Session, bed_id: int) -> BedOut:
    bed = db.get(Bed, bed_id)
    if bed is None:
        raise not_found(_BED_NOT_FOUND)
    return _bed_out(db, bed)


def create_bed(db: Session, data: BedCreate, user: User) -> BedOut:
    _check_code(db, Bed, _BED_LABEL, data.code, None)
    bed = Bed(code=data.code, area=data.area)
    db.add(bed)
    _flush(
        db,
        DomainError(
            "DUPLICATE_CODE", f"{_BED_LABEL} {data.code} đã tồn tại", 409, {"field": "code"}
        ),
    )
    _audit(db, user, "bed.create", bed, None, _bed_snapshot(bed))
    db.commit()
    return _bed_out(db, bed)


def update_bed(db: Session, bed_id: int, data: BedUpdate, user: User) -> BedOut:
    bed = _locked(db, Bed, bed_id, _BED_NOT_FOUND)
    before = _bed_snapshot(bed)
    if data.code is not None and data.code != bed.code:
        _check_code(db, Bed, _BED_LABEL, data.code, bed.id)
        bed.code = data.code
    if data.area is not None:
        bed.area = data.area
    after = _bed_snapshot(bed)
    if after != before:
        _flush(
            db,
            DomainError(
                "DUPLICATE_CODE", f"{_BED_LABEL} {bed.code} đã tồn tại", 409, {"field": "code"}
            ),
        )
        _audit(db, user, "bed.update", bed, before, after)
    db.commit()
    return _bed_out(db, bed)


def delete_bed(db: Session, bed_id: int, user: User) -> BedOut:
    bed = _locked(db, Bed, bed_id, _BED_NOT_FOUND)
    if bed.is_active:
        session = _open_session(db, bed_id=bed.id)
        if session is not None:
            raise DomainError(
                "BED_HAS_OPEN_SESSION",
                f"Giường {bed.code} đang có phiên theo dõi. Kết thúc phiên trước khi xóa.",
                409,
                {"session_id": session.id},
            )
        before = _bed_snapshot(bed)
        bed.is_active = False  # giữ liên kết camera (R15)
        _audit(db, user, "bed.delete", bed, before, _bed_snapshot(bed))
    db.commit()
    return _bed_out(db, bed)


def restore_bed(db: Session, bed_id: int, user: User) -> BedOut:
    bed = _locked(db, Bed, bed_id, _BED_NOT_FOUND)
    if not bed.is_active:
        before = _bed_snapshot(bed)
        bed.is_active = True
        _audit(db, user, "bed.restore", bed, before, _bed_snapshot(bed))
    db.commit()
    return _bed_out(db, bed)


# ---------- Bệnh nhân ----------

_PATIENT_LABEL = "Mã thử nghiệm"
_PATIENT_NOT_FOUND = "Không tìm thấy bệnh nhân"


def _patient_snapshot(p: Patient) -> dict[str, Any]:
    return {"code": p.code, "note": p.note, "is_active": p.is_active}


def _patient_out(db: Session, p: Patient) -> PatientOut:
    session = _open_session(db, patient_id=p.id)
    return patient_out(p, session.id if session else None)


def _clean_note(note: str | None) -> str | None:
    return note or None  # chuỗi rỗng sau khi bỏ khoảng trắng = không có ghi chú


def list_patients(
    db: Session, include_inactive: bool = False, limit: int = 50, offset: int = 0
) -> Page[PatientOut]:
    q = select(Patient).order_by(Patient.code)
    if not include_inactive:
        q = q.where(Patient.is_active.is_(True))
    by_patient = {s.patient_id: s.id for s in _active_sessions(db)}
    return _page(db, q, limit, offset, lambda p: patient_out(p, by_patient.get(p.id)))


def get_patient(db: Session, patient_id: int) -> PatientOut:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise not_found(_PATIENT_NOT_FOUND)
    return _patient_out(db, patient)


def create_patient(db: Session, data: PatientCreate, user: User) -> PatientOut:
    _check_code(db, Patient, _PATIENT_LABEL, data.code, None)
    patient = Patient(code=data.code, note=_clean_note(data.note))
    db.add(patient)
    _flush(
        db,
        DomainError(
            "DUPLICATE_CODE", f"{_PATIENT_LABEL} {data.code} đã tồn tại", 409, {"field": "code"}
        ),
    )
    _audit(db, user, "patient.create", patient, None, _patient_snapshot(patient))
    db.commit()
    return _patient_out(db, patient)


def update_patient(db: Session, patient_id: int, data: PatientUpdate, user: User) -> PatientOut:
    patient = _locked(db, Patient, patient_id, _PATIENT_NOT_FOUND)
    before = _patient_snapshot(patient)
    if data.code is not None and data.code != patient.code:
        _check_code(db, Patient, _PATIENT_LABEL, data.code, patient.id)
        patient.code = data.code
    if "note" in data.model_fields_set:
        patient.note = _clean_note(data.note)
    after = _patient_snapshot(patient)
    if after != before:
        _flush(
            db,
            DomainError(
                "DUPLICATE_CODE",
                f"{_PATIENT_LABEL} {patient.code} đã tồn tại",
                409,
                {"field": "code"},
            ),
        )
        _audit(db, user, "patient.update", patient, before, after)
    db.commit()
    return _patient_out(db, patient)


def delete_patient(db: Session, patient_id: int, user: User) -> PatientOut:
    patient = _locked(db, Patient, patient_id, _PATIENT_NOT_FOUND)
    if patient.is_active:
        session = _open_session(db, patient_id=patient.id)
        if session is not None:
            raise DomainError(
                "PATIENT_HAS_OPEN_SESSION",
                f"Bệnh nhân {patient.code} đang được theo dõi. Kết thúc phiên trước khi xóa.",
                409,
                {"session_id": session.id},
            )
        before = _patient_snapshot(patient)
        patient.is_active = False
        _audit(db, user, "patient.delete", patient, before, _patient_snapshot(patient))
    db.commit()
    return _patient_out(db, patient)


def restore_patient(db: Session, patient_id: int, user: User) -> PatientOut:
    patient = _locked(db, Patient, patient_id, _PATIENT_NOT_FOUND)
    if not patient.is_active:
        before = _patient_snapshot(patient)
        patient.is_active = True
        _audit(db, user, "patient.restore", patient, before, _patient_snapshot(patient))
    db.commit()
    return _patient_out(db, patient)


# ---------- Camera ----------

_CAMERA_NOT_FOUND = "Không tìm thấy camera"


def _camera_snapshot(c: Camera) -> dict[str, Any]:
    return {
        "name": c.name,
        "source_type": c.source_type,
        "source": c.source,
        "bed_id": c.bed_id,
        "is_active": c.is_active,
        "config_version": c.config_version,
    }


def _camera_out(db: Session, c: Camera) -> CameraOut:
    db.refresh(c)
    return camera_out(c)


def _clean_source(source_type: CameraSourceType, source: str) -> str:
    """Kiểm tra `source` theo loại (R5, giả định). Không kiểm tra file tồn tại."""
    value = source.strip()
    if source_type == CameraSourceType.WEBCAM:
        ok = re.fullmatch(r"\d+", value) is not None
        message = "Webcam cần số thứ tự là số nguyên không âm (ví dụ 0)"
    elif source_type == CameraSourceType.URL:
        ok = value.lower().startswith(_URL_PREFIXES) and len(value) > len("http://")
        message = "Địa chỉ stream phải bắt đầu bằng http://, https:// hoặc rtsp://"
    else:
        ok = value != ""
        message = "Cần nhập đường dẫn file video"
    if not ok:
        raise validation_error(message, {"field": "source"})
    return str(int(value)) if source_type == CameraSourceType.WEBCAM else value


def _bed_has_camera(camera_id: int, code: str) -> DomainError:
    return DomainError(
        "BED_ALREADY_HAS_CAMERA",
        f"Giường {code} đã có camera. Gỡ camera đó trước khi gắn camera khác.",
        409,
        {"camera_id": camera_id},
    )


def _camera_in_session(camera: Camera, session: MonitoringSession, action: str) -> DomainError:
    """Camera là `camera_id` của phiên đang mở: không xóa, không đổi giường/nguồn (R14)."""
    return DomainError(
        "CAMERA_IN_ACTIVE_SESSION",
        f'Camera "{camera.name}" đang dùng cho một phiên theo dõi. '
        f"Kết thúc phiên trước khi {action}.",
        409,
        {"session_id": session.id},
    )


def _check_bed_free(db: Session, bed_id: int, own_id: int | None) -> Bed:
    bed = db.get(Bed, bed_id)
    if bed is None:
        raise not_found(_BED_NOT_FOUND)
    if not bed.is_active:
        raise validation_error(f"Giường {bed.code} đã bị xóa", {"field": "bed_id"})
    other = db.scalar(select(Camera).where(Camera.bed_id == bed_id))
    if other is not None and other.id != own_id:
        raise _bed_has_camera(other.id, bed.code)
    return bed


def list_cameras(
    db: Session, include_inactive: bool = False, limit: int = 50, offset: int = 0
) -> Page[CameraOut]:
    q = select(Camera).options(selectinload(Camera.bed)).order_by(Camera.id)
    if not include_inactive:
        q = q.where(Camera.is_active.is_(True))
    return _page(db, q, limit, offset, camera_out)


def get_camera(db: Session, camera_id: int) -> CameraOut:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise not_found(_CAMERA_NOT_FOUND)
    return camera_out(camera)


def create_camera(db: Session, data: CameraCreate, user: User) -> CameraOut:
    source = _clean_source(data.source_type, data.source)
    bed = _check_bed_free(db, data.bed_id, None) if data.bed_id is not None else None
    camera = Camera(name=data.name, source_type=data.source_type, source=source, bed_id=data.bed_id)
    db.add(camera)
    _flush(db, _bed_has_camera(0, bed.code if bed else ""))
    _audit(db, user, "camera.create", camera, None, _camera_snapshot(camera))
    db.commit()
    return _camera_out(db, camera)


def update_camera(db: Session, camera_id: int, data: CameraUpdate, user: User) -> CameraOut:
    camera = _locked(db, Camera, camera_id, _CAMERA_NOT_FOUND)
    before = _camera_snapshot(camera)
    fields = data.model_fields_set
    source_type = data.source_type or camera.source_type
    source = data.source if data.source is not None else camera.source
    if "source_type" in fields or "source" in fields:
        camera.source = _clean_source(source_type, source)
        camera.source_type = source_type
    if data.name is not None:
        camera.name = data.name
    bed_code = ""
    if "bed_id" in fields and data.bed_id != camera.bed_id:
        if data.bed_id is not None:
            if not camera.is_active:
                raise validation_error(
                    "Camera đã bị xóa. Khôi phục camera trước khi gắn giường.", {"field": "bed_id"}
                )
            bed_code = _check_bed_free(db, data.bed_id, camera.id).code
        camera.bed_id = data.bed_id
    if any(before[f] != _camera_snapshot(camera)[f] for f in _CAMERA_CONFIG_FIELDS):
        session = _open_session(db, camera_id=camera.id)
        if session is not None:
            db.rollback()  # bỏ thay đổi trong bộ nhớ, nhả khóa hàng
            raise _camera_in_session(camera, session, "sửa giường hoặc nguồn")
        camera.config_version += 1
    after = _camera_snapshot(camera)
    if after != before:
        _flush(db, _bed_has_camera(0, bed_code))
        _audit(db, user, "camera.update", camera, before, after)
    db.commit()
    return _camera_out(db, camera)


def delete_camera(db: Session, camera_id: int, user: User) -> CameraOut:
    camera = _locked(db, Camera, camera_id, _CAMERA_NOT_FOUND)
    if camera.is_active:
        session = _open_session(db, camera_id=camera.id)
        if session is not None:
            raise _camera_in_session(camera, session, "xóa")
        before = _camera_snapshot(camera)
        camera.is_active = False
        if camera.bed_id is not None:
            # Giải phóng giường để gắn camera khác; giá trị cũ nằm trong audit `before` (R15).
            camera.bed_id = None
            camera.config_version += 1
        _audit(db, user, "camera.delete", camera, before, _camera_snapshot(camera))
    db.commit()
    return _camera_out(db, camera)


def restore_camera(db: Session, camera_id: int, user: User) -> CameraOut:
    """Không tự gắn lại giường cũ (R15)."""
    camera = _locked(db, Camera, camera_id, _CAMERA_NOT_FOUND)
    if not camera.is_active:
        before = _camera_snapshot(camera)
        camera.is_active = True
        _audit(db, user, "camera.restore", camera, before, _camera_snapshot(camera))
    db.commit()
    return _camera_out(db, camera)
