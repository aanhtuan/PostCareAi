"""F04 AC2, AC6 (R4, R14, R16): ràng buộc DB và yêu cầu đồng thời.

- Chèn thẳng bằng SQLAlchemy để chứng minh partial unique index và `UNIQUE (previous_session_id)`
  chặn ở mức DB, không chỉ ở domain.
- Test đồng thời dùng commit thật (`real_commit`), mỗi luồng một kết nối riêng.
"""

import threading
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from postcare.db.models import Bed, MonitoringSession, Patient, User
from postcare.db.types import utcnow
from postcare.domain import sessions as svc
from postcare.domain.errors import DomainError
from postcare.domain.notifications import InMemoryPublisher

Login = Callable[[str], dict[str, str]]


def _ids(db: Session) -> tuple[int, int, int, int, int]:
    user = db.scalar(select(User.id).where(User.username == "nurse"))
    b1, b2 = db.scalars(select(Bed.id).order_by(Bed.id).limit(2)).all()
    p1, p2 = db.scalars(select(Patient.id).order_by(Patient.id).limit(2)).all()
    assert user is not None
    return user, b1, b2, p1, p2


def _row(user: int, bed: int, patient: int, **kw: Any) -> MonitoringSession:
    return MonitoringSession(
        bed_id=bed, patient_id=patient, started_at=utcnow(), started_by=user, **kw
    )


def test_db_partial_unique_blocks_duplicate_open_session(client: TestClient, db: Session) -> None:
    user, b1, b2, p1, p2 = _ids(db)
    db.add(_row(user, b1, p1))
    db.flush()
    for bed, patient in ((b1, p2), (b2, p1)):
        nested = db.begin_nested()
        db.add(_row(user, bed, patient))
        with pytest.raises(IntegrityError):
            db.flush()
        nested.rollback()


def test_db_closed_session_does_not_block(client: TestClient, db: Session) -> None:
    user, b1, _, p1, _ = _ids(db)
    db.add(_row(user, b1, p1, ended_at=utcnow(), ended_by=user))
    db.add(_row(user, b1, p1))
    db.flush()


def test_db_previous_session_id_unique(client: TestClient, db: Session) -> None:
    """Chuỗi chuyển giường tuyến tính: một phiên chỉ có tối đa một phiên sau."""
    user, b1, b2, p1, p2 = _ids(db)
    first = _row(user, b1, p1, ended_at=utcnow(), ended_by=user)
    db.add(first)
    db.flush()
    db.add(_row(user, b2, p1, previous_session_id=first.id, transfer_reason="a"))
    db.flush()
    db.add(_row(user, b1, p2, previous_session_id=first.id, transfer_reason="b"))
    with pytest.raises(IntegrityError):
        db.flush()


def _race(app: Any, calls: list[Callable[[Session, User], Any]]) -> list[Any]:
    """Chạy các lời gọi domain đồng thời, mỗi luồng một session DB riêng (commit thật)."""
    barrier = threading.Barrier(len(calls))
    results: list[Any] = [None] * len(calls)

    def run(i: int, fn: Callable[[Session, User], Any]) -> None:
        with app.state.session_factory() as db:
            user = db.scalars(select(User).where(User.username == "nurse")).one()
            barrier.wait()
            try:
                results[i] = fn(db, user)
            except DomainError as exc:
                results[i] = exc

    threads = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(calls)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return results


@pytest.mark.real_commit
def test_concurrent_start_same_bed_one_wins(app: Any, client: TestClient) -> None:
    pub = InMemoryPublisher()
    results = _race(
        app,
        [
            lambda db, u, p=p: svc.start_session(db, bed_id=1, patient_id=p, user=u, publisher=pub)
            for p in (1, 2)
        ],
    )
    errors = [r for r in results if isinstance(r, DomainError)]
    assert len(errors) == 1, results
    assert errors[0].code == "SESSION_ALREADY_OPEN"


@pytest.mark.real_commit
def test_concurrent_transfer_same_target_one_wins(
    app: Any, client: TestClient, login: Login
) -> None:
    nurse = login("nurse")
    s1 = client.post("/api/v1/sessions", json={"bed_id": 1, "patient_id": 1}, headers=nurse).json()
    s2 = client.post("/api/v1/sessions", json={"bed_id": 2, "patient_id": 2}, headers=nurse).json()
    pub = InMemoryPublisher()
    results = _race(
        app,
        [
            lambda db, u, sid=sid: svc.transfer_session(
                db, session_id=sid, target_bed_id=3, reason="Đồng thời", user=u, publisher=pub
            )
            for sid in (s1["id"], s2["id"])
        ],
    )
    errors = [r for r in results if isinstance(r, DomainError)]
    assert len(errors) == 1, results
    assert errors[0].code == "SESSION_ALREADY_OPEN"
    with app.state.session_factory() as db:
        open_rows = db.scalars(
            select(MonitoringSession).where(MonitoringSession.ended_at.is_(None))
        ).all()
        # bên thua giữ phiên cũ mở; bên thắng có phiên mới ở giường 3
        assert sorted(s.bed_id for s in open_rows) in ([1, 3], [2, 3])
