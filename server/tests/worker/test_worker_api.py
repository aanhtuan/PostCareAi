"""F06 tích hợp worker ↔ API: worker dùng `TestClient` của FastAPI làm `httpx.Client` (R12).

Video tổng hợp chỉ tạo trong `tmp_path` (không commit media). Adapter pose giả (không cần model),
engine thật với cấu hình mặc định.
"""

from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from postcare.worker.client import WorkerApiClient
from postcare.worker.config import WorkerConfig
from postcare.worker.loop import Worker, WorkerOptions, default_engine_factory
from sqlalchemy import update
from sqlalchemy.orm import Session

from postcare.db.models import Camera
from postcare.domain.cameras import mark_offline_cameras
from postcare.domain.notifications import InMemoryPublisher
from postcare.settings import REPO_ROOT
from postcare.vision.camera import FileSource
from postcare.vision.inference.fake import FakePoseAdapter
from tests.camera.synthetic import write_video
from tests.conftest import WORKER_TOKEN
from tests.worker.helpers import ROI, FakeTime

ENGINE_DEFAULT = REPO_ROOT / "config" / "engine.default.yaml"


def _make_worker(client: TestClient, video: Path) -> tuple[Worker, FakeTime]:
    t = FakeTime()

    def source_factory(cfg: WorkerConfig) -> FileSource:
        return FileSource(video, max_fps=15)

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


def _run(worker: Worker, t: FakeTime, until_rel: float) -> None:
    end = 100.0 + until_rel
    for _ in range(100_000):
        if t.t >= end:
            return
        worker.step()
    raise AssertionError("worker không tiến thời gian")


def _set_roi(db: Session) -> None:
    db.execute(update(Camera).where(Camera.id == 1).values(roi_polygon=ROI))
    db.commit()


def test_worker_online_then_offline(
    app: Any,
    client: TestClient,
    db: Session,
    publisher: InMemoryPublisher,
    open_session: dict[str, Any],
    tmp_path: Path,
) -> None:
    _set_roi(db)
    video = write_video(tmp_path / "clip.avi", n_frames=90, fps=15.0, size=(64, 48))
    worker, t = _make_worker(client, video)
    _run(worker, t, 4.0)
    db.expire_all()
    cam = db.get(Camera, 1)
    assert cam is not None and cam.status == "ONLINE"
    assert cam.last_seen_at is not None
    # Engine thật chạy trong worker: không có người → trạng thái giường NO_OBSERVATION trong RAM.
    state = app.state.store.get_bed_state(1)
    assert state is not None and state.body_state == "NO_OBSERVATION"
    assert app.state.frames.get(1) is not None
    runtime = client.get("/api/v1/cameras/1", headers=_nurse(client)).json()["runtime"]
    assert runtime["source_status"] == "ONLINE"

    worker.close()
    changed = mark_offline_cameras(
        db,
        app.state.store,
        publisher,
        offline_after_s=5,
        now=cam.last_seen_at + timedelta(seconds=6),
    )
    assert changed == [1]
    db.expire_all()
    assert db.get(Camera, 1).status == "OFFLINE"  # type: ignore[union-attr]


def test_worker_reloads_config_within_5s_api(
    client: TestClient, db: Session, tmp_path: Path, login: Any
) -> None:
    _set_roi(db)
    video = write_video(tmp_path / "clip.avi", n_frames=300, fps=15.0, size=(64, 48))
    worker, t = _make_worker(client, video)
    _run(worker, t, 2.5)
    assert worker.config is not None and worker.config.config_version == 1
    r = client.patch(
        "/api/v1/cameras/1",
        headers=login("admin"),
        json={"source_type": "URL", "source": "http://192.168.1.50:4747/video"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["config_version"] == 2
    changed_at = t.t
    for _ in range(100_000):
        if worker.config.config_version == 2:
            break
        worker.step()
    assert t.t - changed_at <= 5.0
    assert worker.config.source == "http://192.168.1.50:4747/video"
    worker.close()


def _nurse(client: TestClient) -> dict[str, str]:
    from tests.conftest import PASSWORD

    r = client.post("/api/v1/auth/login", json={"username": "nurse", "password": PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
