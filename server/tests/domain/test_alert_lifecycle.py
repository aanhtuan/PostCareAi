"""F19 AC2, R1–R4: tranh chấp vòng đời cảnh báo với hai session DB thật (commit thật).

- `acknowledge`: UPDATE có điều kiện → đúng một người thắng, người kia 409 có tên.
- `resolve`/`outcome`: khóa dòng alert trước khi kiểm tra trạng thái, nên không có hai lần
  "Đã xử lý" hay ghi kết quả sau khi đã xử lý.
"""

import threading
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from postcare.db.models import Alert, AuditLog, User
from postcare.domain import alerts as svc
from postcare.domain.errors import DomainError
from postcare.domain.notifications import InMemoryPublisher
from postcare.schemas.enums import AlertOutcome, AlertStatus

Login = Callable[[str], dict[str, str]]
Call = Callable[[Session, User], Any]


def _race(app: Any, calls: list[tuple[str, Call]]) -> list[Any]:
    """Mỗi luồng một session DB riêng, chạy cùng lúc nhờ barrier."""
    barrier = threading.Barrier(len(calls))
    results: list[Any] = [None] * len(calls)

    def run(i: int, username: str, fn: Call) -> None:
        with app.state.session_factory() as db:
            user = db.scalars(select(User).where(User.username == username)).one()
            barrier.wait()
            try:
                results[i] = fn(db, user)
            except DomainError as exc:
                results[i] = exc

    threads = [
        threading.Thread(target=run, args=(i, name, fn)) for i, (name, fn) in enumerate(calls)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return results


def _alert(client: TestClient, login: Login, post_event: Callable[..., Any]) -> int:
    assert post_event("BED_EXIT", "HIGH").status_code == 201
    items = client.get("/api/v1/alerts", headers=login("nurse")).json()["items"]
    return max(i["id"] for i in items)


def _audit_actions(app: Any, aid: int) -> list[str]:
    with app.state.session_factory() as db:
        return list(
            db.scalars(
                select(AuditLog.action)
                .where(AuditLog.entity_type == "alert", AuditLog.entity_id == aid)
                .order_by(AuditLog.id)
            )
        )


@pytest.mark.real_commit
@pytest.mark.parametrize("_round", range(3))
def test_conditional_update_only_one_winner(
    app: Any,
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    post_event: Callable[..., Any],
    _round: int,
) -> None:
    aid = _alert(client, login, post_event)
    pub = InMemoryPublisher()
    results = _race(
        app,
        [(name, lambda db, u: svc.acknowledge(db, aid, u, pub)) for name in ("nurse", "charge")],
    )
    errors = [r for r in results if isinstance(r, DomainError)]
    wins = [r for r in results if not isinstance(r, DomainError)]
    assert len(errors) == 1 and len(wins) == 1, results
    winner = wins[0].acknowledged_by.full_name
    assert errors[0].code == "ALERT_ALREADY_ACKNOWLEDGED"
    assert errors[0].http_status == 409
    assert winner in errors[0].message
    assert errors[0].details["acknowledged_by"]["full_name"] == winner
    assert _audit_actions(app, aid).count("alert.acknowledge") == 1
    assert pub.types() == ["alert.updated"]


@pytest.mark.real_commit
@pytest.mark.parametrize("_round", range(3))
def test_concurrent_resolve_only_one_winner(
    app: Any,
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    post_event: Callable[..., Any],
    _round: int,
) -> None:
    aid = _alert(client, login, post_event)
    assert (
        client.post(f"/api/v1/alerts/{aid}/acknowledge", headers=login("nurse")).status_code == 200
    )
    pub = InMemoryPublisher()
    results = _race(
        app,
        [(name, lambda db, u: svc.resolve(db, aid, None, u, pub)) for name in ("nurse", "charge")],
    )
    errors = [r for r in results if isinstance(r, DomainError)]
    assert len(errors) == 1, results
    assert errors[0].code == "INVALID_ALERT_TRANSITION"
    assert _audit_actions(app, aid).count("alert.resolve") == 1
    assert pub.types() == ["alert.updated"]


@pytest.mark.real_commit
@pytest.mark.parametrize("_round", range(3))
def test_concurrent_outcome_and_resolve_never_outcome_after_resolved(
    app: Any,
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    post_event: Callable[..., Any],
    _round: int,
) -> None:
    aid = _alert(client, login, post_event)
    assert (
        client.post(f"/api/v1/alerts/{aid}/acknowledge", headers=login("nurse")).status_code == 200
    )
    pub = InMemoryPublisher()
    results = _race(
        app,
        [
            ("nurse", lambda db, u: svc.resolve(db, aid, None, u, pub)),
            (
                "charge",
                lambda db, u: svc.set_outcome(db, aid, AlertOutcome.CONFIRMED, None, u, pub),
            ),
        ],
    )
    resolved, outcome = results
    assert not isinstance(resolved, DomainError), results
    with app.state.session_factory() as db:
        row = db.get(Alert, aid)
        assert row is not None and row.status == AlertStatus.RESOLVED
        if isinstance(outcome, DomainError):
            assert outcome.code == "INVALID_ALERT_TRANSITION"
            assert row.outcome is None
        else:
            # Ghi kết quả thắng khóa trước → nằm trước lần xử lý.
            assert row.outcome == AlertOutcome.CONFIRMED
            assert row.outcome_at is not None and row.resolved_at is not None
            assert row.outcome_at <= row.resolved_at
            assert _audit_actions(app, aid)[-2:] == ["alert.outcome", "alert.resolve"]


def test_locked_read_refreshes_stale_identity_map(
    client: TestClient,
    login: Login,
    open_session: dict[str, Any],
    post_event: Callable[..., Any],
    db: Session,
) -> None:
    """Đọc khóa dòng phải nạp lại trạng thái từ DB, không dùng bản Alert cũ trong session."""
    aid = _alert(client, login, post_event)
    ack = client.post(f"/api/v1/alerts/{aid}/acknowledge", headers=login("nurse"))
    assert ack.status_code == 200
    stale = db.get(Alert, aid)
    assert stale is not None and stale.status == AlertStatus.ACKNOWLEDGED
    # Thay đổi ngoài ORM: identity map vẫn giữ ACKNOWLEDGED.
    db.execute(text("UPDATE alerts SET status = 'RESOLVED' WHERE id = :id"), {"id": aid})
    assert stale.status == AlertStatus.ACKNOWLEDGED
    user = db.scalars(select(User).where(User.username == "charge")).one()
    pub = InMemoryPublisher()
    with pytest.raises(DomainError) as exc:
        svc.resolve(db, aid, None, user, pub)
    assert exc.value.code == "INVALID_ALERT_TRANSITION"
    with pytest.raises(DomainError) as exc:
        svc.set_outcome(db, aid, AlertOutcome.CONFIRMED, None, user, pub)
    assert exc.value.code == "INVALID_ALERT_TRANSITION"
    assert pub.messages == []
