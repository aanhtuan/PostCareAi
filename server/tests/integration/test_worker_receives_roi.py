"""F08 AC4 (A02): ADMIN lưu ROI / ngưỡng qua API thật → worker (F06) dùng cấu hình mới ≤5 s.

Worker thật + engine thật, `TestClient` làm `httpx.Client`, đồng hồ giả (không chờ thật).
"""

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from postcare.db.models import Camera
from postcare.engine import Engine
from postcare.settings import REPO_ROOT
from postcare.vision.fake import FakeFrameSource
from postcare.vision.inference.fake import FakePoseAdapter
from postcare.worker.client import WorkerApiClient
from postcare.worker.config import WorkerConfig
from postcare.worker.loop import Worker, WorkerOptions, default_engine_factory
from tests.conftest import WORKER_TOKEN
from tests.engine.builders import BED_ROI, IMAGE_SIZE
from tests.worker.helpers import FakeTime

Login = Callable[[str], dict[str, str]]
ENGINE_DEFAULT = REPO_ROOT / "config" / "engine.default.yaml"
NEW_ROI = [[0.1, 0.15], [0.9, 0.15], [0.9, 0.95], [0.1, 0.95]]


def _worker(client: TestClient) -> tuple[Worker, FakeTime]:
    t = FakeTime()
    script = list(range(0, 600_000, 66))  # ~15 fps, đủ dài cho cả test

    def source_factory(cfg: WorkerConfig) -> FakeFrameSource:
        return FakeFrameSource(script, size=IMAGE_SIZE)

    worker = Worker(
        WorkerApiClient(client, camera_id=1, token=WORKER_TOKEN),
        engine_factory=default_engine_factory(ENGINE_DEFAULT),
        source_factory=source_factory,
        adapter_factory=lambda cfg: FakePoseAdapter({}),
        options=WorkerOptions(),
        clock=t.monotonic,
        wall=t.wall,
        sleep=t.sleep,
        pace=lambda _src: True,
    )
    return worker, t


def _run_until(worker: Worker, t: FakeTime, done: Callable[[], bool], max_s: float) -> float:
    """Chạy worker tới khi `done()` hoặc hết `max_s` giây giả; trả số giây đã chạy."""
    start = t.t
    for _ in range(200_000):
        if done():
            return t.t - start
        if t.t - start > max_s:
            break
        worker.step()
    return t.t - start


def _set_roi(db: Session) -> None:
    roi = [list(p) for p in BED_ROI.points]
    db.execute(update(Camera).where(Camera.id == 1).values(roi_polygon=roi))
    db.commit()


def _engine(worker: Worker) -> Engine:
    assert isinstance(worker.engine, Engine)
    return worker.engine


def test_worker_receives_roi_within_5s(
    client: TestClient, login: Login, db: Session, open_session: dict[str, Any]
) -> None:
    _set_roi(db)
    worker, t = _worker(client)
    _run_until(worker, t, lambda: worker.engine is not None, max_s=10)
    old_engine = _engine(worker)
    assert worker.config is not None
    v0 = worker.config.config_version

    r = client.put("/api/v1/cameras/1/roi", json={"roi_polygon": NEW_ROI}, headers=login("admin"))
    assert r.status_code == 200, r.text

    def reloaded() -> bool:
        cfg = worker.config
        return cfg is not None and cfg.config_version > v0 and worker.engine is not old_engine

    elapsed = _run_until(worker, t, reloaded, max_s=10)
    assert reloaded(), "worker không tải lại cấu hình"
    assert elapsed <= 5.0
    assert worker.config is not None and worker.config.roi_polygon == NEW_ROI
    assert [list(p) for p in _engine(worker).context.roi_polygon.points] == NEW_ROI
    worker.close()


def test_worker_receives_thresholds_within_5s(
    client: TestClient, login: Login, db: Session, open_session: dict[str, Any]
) -> None:
    _set_roi(db)
    worker, t = _worker(client)
    _run_until(worker, t, lambda: worker.engine is not None, max_s=10)
    overrides = {"posture": {"lying_enter_deg": 20}}
    r = client.put(
        "/api/v1/cameras/1/thresholds", json={"thresholds": overrides}, headers=login("admin")
    )
    assert r.status_code == 200, r.text

    def reloaded() -> bool:
        return worker.engine is not None and _engine(worker).config.posture.lying_enter_deg == 20

    elapsed = _run_until(worker, t, reloaded, max_s=10)
    assert reloaded() and elapsed <= 5.0
    worker.close()


def test_worker_keeps_config_when_nothing_saved(
    client: TestClient, db: Session, open_session: dict[str, Any]
) -> None:
    _set_roi(db)
    worker, t = _worker(client)
    _run_until(worker, t, lambda: worker.engine is not None, max_s=10)
    engine = worker.engine
    assert worker.config is not None
    version = worker.config.config_version
    _run_until(worker, t, lambda: False, max_s=12)
    assert worker.engine is engine
    assert worker.config is not None and worker.config.config_version == version
    worker.close()
