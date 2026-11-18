"""F31 AC1, AC2: nhiều worker thật (engine thật, nguồn/pose giả) ↔ một API thật, chạy xen kẽ.

Mỗi worker có đồng hồ giả riêng (như mỗi tiến trình); bước của worker nào có đồng hồ nhỏ nhất
thì chạy trước. Worker "chết" = ngừng gọi `step()` (như tiến trình bị dừng).
"""

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from postcare.db.models import Bed, Camera, Event
from postcare.domain.cameras import mark_offline_cameras
from postcare.vision.camera import SourceOpenError
from postcare.vision.fake import FakeFrameSource
from postcare.vision.inference.fake import FakePoseAdapter
from postcare.worker.client import WorkerApiClient
from postcare.worker.config import WorkerConfig
from postcare.worker.loop import Worker, WorkerOptions, default_engine_factory
from tests.conftest import WORKER_TOKEN
from tests.engine.builders import BED_ROI, IMAGE_SIZE
from tests.integration.test_worker_events import (
    ENGINE_CODES,
    ENGINE_DEFAULT,
    NowFakeTime,
    _sequence,
)

CAMERAS = (1, 2, 3)
EXIT_CODES = ["SIT_UP", "BED_EDGE", "STAND_UP", "BED_EXIT"]
TAIL_FRAMES = 150  # 10 s ở 15 fps


class _CrashError(RuntimeError):
    pass


class _CrashingAdapter(FakePoseAdapter):
    """Adapter giả lỗi sau `after` khung (giống tiến trình worker gặp lỗi không bắt)."""

    def __init__(self, persons: dict[int, Any], after: int) -> None:
        super().__init__(persons)
        self._left = after

    def observe(self, frame: Any, camera_id: int) -> Any:
        self._left -= 1
        if self._left < 0:
            raise _CrashError("adapter lỗi")
        return super().observe(frame, camera_id)


def _worker(
    client: TestClient,
    camera_id: int,
    *,
    source_fails: bool = False,
    crash_after: int | None = None,
) -> tuple[Worker, NowFakeTime]:
    t = NowFakeTime()
    seq = _sequence()
    persons = {obs.frame_index: obs.persons for obs in seq}
    script = [obs.ts_ms for obs in seq]
    # Nguồn còn chạy sau chuỗi (khung không người): hết file thì báo OFFLINE, không cần ở đây.
    script += [script[-1] + 67 * (i + 1) for i in range(TAIL_FRAMES)]

    def source_factory(cfg: WorkerConfig) -> FakeFrameSource:
        assert cfg.camera_id == camera_id
        if source_fails:
            raise SourceOpenError(f"camera {camera_id} mất nguồn")
        return FakeFrameSource(script, size=IMAGE_SIZE)

    def adapter_factory(cfg: WorkerConfig) -> FakePoseAdapter:
        if crash_after is not None:
            return _CrashingAdapter(persons, crash_after)
        return FakePoseAdapter(persons)

    worker = Worker(
        WorkerApiClient(client, camera_id=camera_id, token=WORKER_TOKEN),
        engine_factory=default_engine_factory(ENGINE_DEFAULT),
        source_factory=source_factory,
        adapter_factory=adapter_factory,
        options=WorkerOptions(),
        clock=t.monotonic,
        wall=t.wall,
        sleep=t.sleep,
        pace=lambda _src: True,
    )
    return worker, t


def _run_all(workers: dict[int, tuple[Worker, NowFakeTime]], until_rel: float) -> set[int]:
    """Chạy xen kẽ tới `until_rel` giây; worker ném lỗi coi như tiến trình chết. Trả id đã chết."""
    end = 100.0 + until_rel
    alive = dict(workers)
    dead: set[int] = set()
    for _ in range(600_000):
        running = {cid: wt for cid, wt in alive.items() if wt[1].t < end}
        if not running:
            return dead
        cid, (worker, _t) = min(running.items(), key=lambda kv: kv[1][1].t)
        try:
            worker.step()
        except _CrashError:
            dead.add(cid)
            del alive[cid]
    raise AssertionError("worker không tiến thời gian")


def _prepare(db: Session, client: TestClient, login: Any) -> dict[int, int]:
    """ROI cho 3 camera, phiên mở cho A01–A03. Trả camera_id → session_id."""
    roi = [list(p) for p in BED_ROI.points]
    db.execute(update(Camera).where(Camera.id.in_(CAMERAS)).values(roi_polygon=roi))
    db.commit()
    sessions: dict[int, int] = {}
    for cam_id in CAMERAS:
        cam = db.get(Camera, cam_id)
        assert cam is not None and cam.bed_id is not None
        r = client.post(
            "/api/v1/sessions",
            json={"bed_id": cam.bed_id, "patient_id": cam_id},
            headers=login("nurse"),
        )
        assert r.status_code == 201, r.text
        sessions[cam_id] = r.json()["id"]
    return sessions


def _engine_events(db: Session) -> list[Event]:
    db.expire_all()
    return [
        e
        for e in db.scalars(select(Event).order_by(Event.occurred_at, Event.id))
        if e.code.value in ENGINE_CODES
    ]


def _bed_of(db: Session) -> dict[int, int]:
    return {c.id: c.bed_id for c in db.scalars(select(Camera)) if c.bed_id is not None}


def _status(db: Session, cam_id: int) -> str:
    db.expire_all()
    cam = db.get(Camera, cam_id)
    assert cam is not None
    return cam.status.value


def test_three_workers_events_bound_to_own_bed(client: TestClient, db: Session, login: Any) -> None:
    sessions = _prepare(db, client, login)
    workers = {cid: _worker(client, cid) for cid in CAMERAS}
    duration = _sequence()[-1].ts_ms / 1000 + 3
    assert _run_all(workers, duration) == set()
    for w, _ in workers.values():
        w.close()

    events = _engine_events(db)
    beds = _bed_of(db)
    a01 = db.scalar(select(Bed).where(Bed.code == "A01"))
    assert a01 is not None
    for cid in CAMERAS:
        mine = [e for e in events if e.camera_id == cid]
        assert [e.code.value for e in mine] == EXIT_CODES
        assert all(e.bed_id == beds[cid] and e.session_id == sessions[cid] for e in mine)
    # Ca âm tính: không sự kiện nào của camera 2/3 lọt vào giường A01.
    assert all(e.camera_id == 1 for e in events if e.bed_id == a01.id)
    assert {_status(db, cid) for cid in CAMERAS} == {"ONLINE"}


def test_source_loss_only_affects_own_camera(client: TestClient, db: Session, login: Any) -> None:
    _prepare(db, client, login)
    workers = {cid: _worker(client, cid, source_fails=(cid == 2)) for cid in CAMERAS}
    duration = _sequence()[-1].ts_ms / 1000 + 3
    _run_all(workers, duration)
    for w, _ in workers.values():
        w.close()

    events = _engine_events(db)
    assert [e.code.value for e in events if e.camera_id == 1] == EXIT_CODES
    assert [e.code.value for e in events if e.camera_id == 3] == EXIT_CODES
    assert [e for e in events if e.camera_id == 2] == []
    assert _status(db, 1) == "ONLINE"
    assert _status(db, 3) == "ONLINE"
    assert _status(db, 2) == "OFFLINE"


def test_dead_worker_only_own_camera_offline(
    app: Any, client: TestClient, db: Session, login: Any, publisher: Any
) -> None:
    _prepare(db, client, login)
    workers = {cid: _worker(client, cid, crash_after=(30 if cid == 2 else None)) for cid in CAMERAS}
    duration = _sequence()[-1].ts_ms / 1000 + 3
    assert _run_all(workers, duration) == {2}
    for cid, (w, _) in workers.items():
        if cid != 2:
            w.close()

    events = _engine_events(db)
    assert [e.code.value for e in events if e.camera_id == 1] == EXIT_CODES
    assert [e.code.value for e in events if e.camera_id == 3] == EXIT_CODES

    # Worker 2 chết: heartbeat cuối của nó cũ hơn ngưỡng A02, của camera 1, 3 thì vẫn mới.
    db.expire_all()
    seen = {cid: db.get(Camera, cid).last_seen_at for cid in CAMERAS}  # type: ignore[union-attr]
    assert all(s is not None for s in seen.values())
    now = max(s for s in seen.values() if s is not None) + timedelta(seconds=1)
    db.execute(
        update(Camera).where(Camera.id == 2).values(last_seen_at=now - timedelta(seconds=10))
    )
    db.commit()
    changed = mark_offline_cameras(db, app.state.store, publisher, offline_after_s=5, now=now)
    assert changed == [2]
    assert _status(db, 1) == "ONLINE"
    assert _status(db, 3) == "ONLINE"
    assert _status(db, 2) == "OFFLINE"
