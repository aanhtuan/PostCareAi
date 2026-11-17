"""F17 AC1, AC3: worker thật (engine thật, `FakeFrameSource` + `FakePoseAdapter`) ↔ API thật.

`TestClient` của FastAPI làm `httpx.Client` cho worker; đồng hồ giả (không chờ thật). Đồng hồ UTC
giả bắt đầu ở thời điểm thật lúc chạy test để `occurred_at` rơi vào phiên vừa mở.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from postcare.db.models import Alert, Camera, Event
from postcare.schemas.enums import AlertStatus
from postcare.settings import REPO_ROOT
from postcare.vision.fake import FakeFrameSource
from postcare.vision.inference.fake import FakePoseAdapter
from postcare.worker.client import WorkerApiClient
from postcare.worker.config import WorkerConfig
from postcare.worker.loop import Worker, WorkerOptions, default_engine_factory
from tests.conftest import WORKER_TOKEN
from tests.engine.builders import BED_ROI, IMAGE_SIZE, STANDING, PoseSequence
from tests.worker.helpers import FakeTime

ENGINE_DEFAULT = REPO_ROOT / "config" / "engine.default.yaml"
ENGINE_CODES = {"SIT_UP", "BED_EDGE", "STAND_UP", "BED_EXIT"}


class NowFakeTime(FakeTime):
    def __init__(self) -> None:
        super().__init__()
        self._wall0 = datetime.now(UTC) + timedelta(milliseconds=50)

    def wall(self) -> datetime:
        return self._wall0 + timedelta(seconds=self.t - 100.0)


def _sequence() -> list[Any]:
    # Cùng chuỗi với test_rules_body.py::test_full_exit_sequence_codes (testing.md mục 2).
    return (
        PoseSequence(fps=15)
        .lying(seconds=4)
        .raise_to_sitting(seconds=1.5)
        .sitting(seconds=3)
        .move_to_edge(seconds=1)
        .hold(seconds=2.5)
        .move_to(STANDING, seconds=0.5)
        .standing(seconds=2)
        .walk_out(seconds=2)
        .hold(seconds=2)
        .build()
    )


def _worker(client: TestClient) -> tuple[Worker, NowFakeTime, list[Any]]:
    t = NowFakeTime()
    seq = _sequence()
    persons = {obs.frame_index: obs.persons for obs in seq}
    script = [obs.ts_ms for obs in seq]

    def source_factory(cfg: WorkerConfig) -> FakeFrameSource:
        return FakeFrameSource(script, size=IMAGE_SIZE)

    worker = Worker(
        WorkerApiClient(client, camera_id=1, token=WORKER_TOKEN),
        engine_factory=default_engine_factory(ENGINE_DEFAULT),
        source_factory=source_factory,
        adapter_factory=lambda cfg: FakePoseAdapter(persons),
        options=WorkerOptions(),
        clock=t.monotonic,
        wall=t.wall,
        sleep=t.sleep,
        pace=lambda _src: True,
    )
    return worker, t, seq


def _run(worker: Worker, t: FakeTime, until_rel: float) -> None:
    end = 100.0 + until_rel
    for _ in range(200_000):
        if t.t >= end:
            return
        worker.step()
    raise AssertionError("worker không tiến thời gian")


def _set_roi(db: Session) -> None:
    roi = [list(p) for p in BED_ROI.points]
    db.execute(update(Camera).where(Camera.id == 1).values(roi_polygon=roi))
    db.commit()


def _engine_events(db: Session) -> list[Event]:
    db.expire_all()
    return [
        e
        for e in db.scalars(select(Event).order_by(Event.occurred_at, Event.id))
        if e.code.value in ENGINE_CODES
    ]


def test_worker_fake_exit_sequence_persists_events(
    client: TestClient, db: Session, open_session: dict[str, Any]
) -> None:
    _set_roi(db)
    worker, t, seq = _worker(client)
    _run(worker, t, seq[-1].ts_ms / 1000 + 3)
    worker.close()
    events = _engine_events(db)
    assert [e.code.value for e in events] == ["SIT_UP", "BED_EDGE", "STAND_UP", "BED_EXIT"]
    for e in events:
        assert e.session_id == open_session["id"]
        assert e.bed_id == 1 and e.camera_id == 1
        assert e.config_hash and e.explanation["rule_id"].startswith("body.")
        assert e.occurred_at <= e.detected_at
    alerts = {
        a.event_id: a
        for a in db.scalars(select(Alert).where(Alert.event_id.in_([e.id for e in events])))
    }
    by_code = {e.code.value: e for e in events}
    assert set(alerts) == {by_code["BED_EDGE"].id, by_code["BED_EXIT"].id}
    assert all(a.status == AlertStatus.PENDING for a in alerts.values())


def test_no_active_session_sends_no_engine_events(client: TestClient, db: Session) -> None:
    _set_roi(db)
    worker, t, seq = _worker(client)
    _run(worker, t, seq[-1].ts_ms / 1000 + 3)
    worker.close()
    assert _engine_events(db) == []
    db.expire_all()
    # Chỉ có thể có sự kiện camera (do API sinh); không có sự kiện engine nào.
    assert all(e.code.value.startswith("CAMERA_") for e in db.scalars(select(Event)))
