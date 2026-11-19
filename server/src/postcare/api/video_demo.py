"""Allowlisted, local video demo. The API supervises a separate, ordinary FILE worker.

Opt-in, single API process only. All clinical/event processing remains in the worker.
Session/audit records survive API restarts; pixels and process handles do not.
"""

import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.api.frame_buffer import LatestFrameStore
from postcare.db.models import Area, AuditLog, Bed, Camera, MonitoringSession, Patient, User
from postcare.domain import sessions
from postcare.domain.audit import record_audit
from postcare.domain.errors import DomainError
from postcare.domain.notifications import Publisher, safe_publish
from postcare.schemas.enums import CameraSourceType, CameraStatus
from postcare.schemas.roi import validate_roi_polygon
from postcare.settings import REPO_ROOT, Settings

CLIP_ID = "pexels-8090735"
VIDEO_PATH = REPO_ROOT / "data/external/pexels/pexels-8090735.mp4"
ROI_PATH = REPO_ROOT / "config/cameras/pexels-8090735.yaml"
DEMO_RUNS_DIR = REPO_ROOT / "runs/video-demo"
DEMO_CODE = "DEMO-VIDEO-8090735"

RunStatus = Literal["RUNNING", "FINISHING", "COMPLETED", "STOPPED", "FAILED", "INTERRUPTED"]


class DemoStartIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clip_id: Literal["pexels-8090735"]


class DemoStopIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: int


class DemoSetupOut(BaseModel):
    bed_id: int
    camera_id: int
    patient_id: int


class DemoRunOut(DemoSetupOut):
    clip_id: Literal["pexels-8090735"] = CLIP_ID
    session_id: int
    started_at: datetime
    status: RunStatus


class DemoStatusOut(BaseModel):
    enabled: bool
    clip_id: Literal["pexels-8090735"] = CLIP_ID
    available: bool
    setup: DemoSetupOut | None = None
    run: DemoRunOut | None = None


def spawn_worker(camera_id: int, session_id: int, settings: Settings) -> subprocess.Popen[bytes]:
    """Never use client paths, shell commands, pipes that may fill, or tokens in argv."""
    log_dir = DEMO_RUNS_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "WORKER_TOKEN": settings.worker_token}
    with (log_dir / f"session-{session_id}.log").open("ab") as log:
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "postcare",
                "worker",
                "--camera-id",
                str(camera_id),
                "--video",
                str(VIDEO_PATH),
                "--api",
                settings.api_base_url,
                "--stop-at-end",
                "--completion-file",
                str(log_dir / f"session-{session_id}.completed"),
            ],
            cwd=REPO_ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt",
        )


def stop_worker(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGINT)
        proc.wait(timeout=8)
    except ProcessLookupError:
        return
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


class VideoDemo:
    def __init__(self, settings: Settings, frames: LatestFrameStore) -> None:
        self.settings = settings
        self.frames = frames
        self.lock = threading.RLock()
        self.proc: subprocess.Popen[bytes] | None = None
        self.run: DemoRunOut | None = None
        self.actor_id: int | None = None
        self.started_at = 0.0

    def _enabled(self) -> None:
        if not self.settings.demo_enabled:
            raise DomainError("NOT_FOUND", "Chế độ demo chưa bật", 404)

    def _ready(self) -> None:
        self._enabled()
        if not VIDEO_PATH.is_file():
            raise DomainError("DEMO_SOURCE_MISSING", "Chưa có clip demo trên máy chủ", 409)

    def _setup(self, db: Session) -> DemoSetupOut | None:
        bed = db.scalar(select(Bed).where(Bed.code == DEMO_CODE))
        patient = db.scalar(select(Patient).where(Patient.code == DEMO_CODE))
        if bed is None or bed.camera is None or patient is None:
            return None
        camera = bed.camera
        owned = db.scalar(
            select(AuditLog.id)
            .where(AuditLog.entity_type == "video_demo_setup", AuditLog.entity_id == camera.id)
            .limit(1)
        )
        if (
            owned is None
            or not bed.is_active
            or not patient.is_active
            or not camera.is_active
            or camera.source_type != CameraSourceType.FILE
            or Path(camera.source) != VIDEO_PATH
            or bed.area.code != "DEMO-VIDEO"
        ):
            raise DomainError(
                "DEMO_CONFIG_CONFLICT", "Cấu hình demo đã thay đổi, cần quản trị kiểm tra", 409
            )
        return DemoSetupOut(bed_id=bed.id, camera_id=camera.id, patient_id=patient.id)

    def prepare(self, db: Session, user: User) -> DemoSetupOut:
        with self.lock:
            self._ready()
            existing = self._setup(db)
            if existing is not None:
                return existing
            # Additive only. Reserved-code collisions fail rather than adopting user records.
            if (
                db.scalar(select(Bed.id).where(Bed.code == DEMO_CODE)) is not None
                or db.scalar(select(Patient.id).where(Patient.code == DEMO_CODE)) is not None
            ):
                raise DomainError("DEMO_CONFIG_CONFLICT", "Mã dữ liệu demo đã được dùng", 409)
            area = db.scalar(select(Area).where(Area.code == "DEMO-VIDEO"))
            # Validate before writes; one commit for the complete dedicated setup.
            roi = validate_roi_polygon(
                yaml.safe_load(ROI_PATH.read_text(encoding="utf-8"))["roi_polygon"]
            )
            if area is None:
                area = Area(code="DEMO-VIDEO", name="Demo video ghi trước")
                db.add(area)
                db.flush()
                record_audit(
                    db,
                    actor_user_id=user.id,
                    action="area.create",
                    entity_type="area",
                    entity_id=area.id,
                    after={"code": area.code, "name": area.name},
                )
            elif not area.is_active:
                raise DomainError("DEMO_CONFIG_CONFLICT", "Khu vực demo đã ngừng dùng", 409)
            bed = Bed(code=DEMO_CODE, area_id=area.id)
            patient = Patient(code=DEMO_CODE, note="Stock footage - diễn viên; Pexels 8090735")
            db.add_all([bed, patient])
            db.flush()
            camera = Camera(
                name="Video Pexels 8090735",
                bed_id=bed.id,
                source_type=CameraSourceType.FILE,
                source=str(VIDEO_PATH),
                roi_polygon=[[x, y] for x, y in roi.points],
            )
            db.add(camera)
            db.flush()
            setup = DemoSetupOut(bed_id=bed.id, camera_id=camera.id, patient_id=patient.id)
            record_audit(
                db,
                actor_user_id=user.id,
                action="demo.prepare",
                entity_type="video_demo_setup",
                entity_id=camera.id,
                after={**setup.model_dump(), "clip_id": CLIP_ID, "roi_polygon": camera.roi_polygon},
            )
            db.commit()
            return setup

    def _latest(self, db: Session) -> DemoRunOut | None:
        entry = db.scalar(
            select(AuditLog)
            .where(AuditLog.entity_type == "video_demo")
            .order_by(AuditLog.id.desc())
            .limit(1)
        )
        if entry is None or entry.after is None:
            return None
        run = DemoRunOut.model_validate(entry.after)
        if run.status in ("RUNNING", "FINISHING"):
            run.status = "INTERRUPTED"  # No owned process after an API restart.
        return run

    def _audit(self, db: Session, user: User, run: DemoRunOut) -> None:
        record_audit(
            db,
            actor_user_id=user.id,
            action=f"demo.{run.status.lower()}",
            entity_type="video_demo",
            entity_id=run.session_id,
            after=run.model_dump(mode="json"),
        )
        db.commit()

    def _finish(
        self, db: Session, publisher: Publisher, user: User, status: RunStatus
    ) -> DemoRunOut:
        assert self.run is not None
        session = db.get(MonitoringSession, self.run.session_id)
        if session is not None and session.ended_at is None:
            sessions.end_session(db, session_id=session.id, user=user, publisher=publisher)
        camera = db.get(Camera, self.run.camera_id)
        if camera is not None:
            # Expected end/stop is not an unexpected camera failure event.
            camera.status = CameraStatus.OFFLINE
        self.run.status = status
        self._audit(db, user, self.run)
        if camera is not None:
            safe_publish(
                publisher,
                "camera.status",
                {
                    "camera_id": camera.id,
                    "bed_id": camera.bed_id,
                    "status": camera.status.value,
                    "fps": None,
                    "brightness": None,
                },
            )
        if status != "FINISHING":
            self.proc = None
        return self.run

    def poll(self, db: Session, publisher: Publisher) -> None:
        with self.lock:
            if self.proc is None:
                return
            code = self.proc.poll()
            assert self.run is not None
            # Successful EOF is signalled before MediaPipe/interpreter cleanup, which can
            # take longer than the camera heartbeat timeout. No events follow this marker.
            completed = (DEMO_RUNS_DIR / f"session-{self.run.session_id}.completed").is_file()
            expired = time.monotonic() - self.started_at >= self.settings.demo_max_run_s
            if code is None and expired:
                stop_worker(self.proc)
                code = 1
            user = db.get(User, self.actor_id)
            assert user is not None
            if code is None:
                if completed and self.run.status == "RUNNING":
                    self._finish(db, publisher, user, "FINISHING")
                return
            self._finish(db, publisher, user, "COMPLETED" if code == 0 else "FAILED")

    def status(self, db: Session, publisher: Publisher) -> DemoStatusOut:
        with self.lock:
            self.poll(db, publisher)
            return DemoStatusOut(
                enabled=self.settings.demo_enabled,
                available=VIDEO_PATH.is_file(),
                setup=self._setup(db),
                run=self.run or self._latest(db),
            )

    def start(self, db: Session, publisher: Publisher, user: User) -> DemoRunOut:
        with self.lock:
            self._ready()
            self.poll(db, publisher)
            previous = self.run or self._latest(db)
            if previous and previous.status in ("RUNNING", "FINISHING", "INTERRUPTED"):
                raise DomainError(
                    "DEMO_ALREADY_RUNNING", "Dừng hoặc đóng lượt demo hiện tại trước", 409
                )
            setup = self.prepare(db, user)
            session = sessions.start_session(
                db, bed_id=setup.bed_id, patient_id=setup.patient_id, user=user, publisher=publisher
            )
            self.run = DemoRunOut(
                **setup.model_dump(),
                session_id=session.id,
                started_at=session.started_at,
                status="RUNNING",
            )
            self.actor_id = user.id
            self._audit(db, user, self.run)
            self.frames.discard(setup.camera_id)
            (DEMO_RUNS_DIR / f"session-{session.id}.completed").unlink(missing_ok=True)
            self.started_at = time.monotonic()
            try:
                self.proc = spawn_worker(setup.camera_id, session.id, self.settings)
            except OSError as exc:
                self._finish(db, publisher, user, "FAILED")
                raise DomainError(
                    "DEMO_START_FAILED", "Không khởi động được phân tích video", 503
                ) from exc
            return self.run

    def stop(self, db: Session, publisher: Publisher, user: User, session_id: int) -> DemoRunOut:
        with self.lock:
            self._enabled()
            self.run = self.run or self._latest(db)
            if self.run is None or session_id != self.run.session_id:
                raise DomainError("DEMO_RUN_CONFLICT", "Lượt demo đã thay đổi, tải lại trang", 409)
            if self.run.status not in ("RUNNING", "FINISHING", "INTERRUPTED"):
                return self.run
            if self.proc is not None:
                stop_worker(self.proc)
            return self._finish(db, publisher, user, "STOPPED")

    def shutdown(self, db: Session, publisher: Publisher) -> None:
        with self.lock:
            if self.proc is not None and self.run is not None:
                user = db.get(User, self.actor_id)
                assert user is not None
                self.stop(db, publisher, user, self.run.session_id)
