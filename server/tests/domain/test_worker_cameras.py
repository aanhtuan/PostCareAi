"""F31 R4 (AC4): danh sách camera mà `postcare workers` khởi động worker."""

from sqlalchemy import update
from sqlalchemy.orm import Session

from postcare.db.models import Bed, Camera
from postcare.domain.cameras import worker_camera_ids
from postcare.schemas.enums import CameraSourceType


def test_all_active_cameras_with_bed(db: Session) -> None:
    assert worker_camera_ids(db) == [1, 2, 3]


def test_skips_inactive_camera_unassigned_camera_and_inactive_bed(db: Session) -> None:
    db.execute(update(Camera).where(Camera.id == 3).values(is_active=False))
    db.add(
        Camera(name="Camera dự phòng", bed_id=None, source_type=CameraSourceType.WEBCAM, source="1")
    )
    db.commit()
    assert worker_camera_ids(db) == [1, 2]
    bed_id = db.get(Camera, 2).bed_id  # type: ignore[union-attr]
    db.execute(update(Bed).where(Bed.id == bed_id).values(is_active=False))
    db.commit()
    assert worker_camera_ids(db) == [1]
