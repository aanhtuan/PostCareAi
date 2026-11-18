"""F29 R5, R6, AC3: chỉ số workflow từ bảng `alerts` (thời điểm biết trước, số tính tay)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from postcare.domain.workflow_metrics import workflow_metrics
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from postcare.db.models import Alert
from postcare.schemas.enums import AlertOutcome, AlertStatus

T0 = datetime(2026, 11, 18, 2, 0, tzinfo=UTC)
END = T0 + timedelta(hours=1)


def _s(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def _seed(db: Session, post_event: Callable[..., Any], n: int) -> list[int]:
    for _ in range(n):
        assert post_event("BED_EXIT", "HIGH").status_code == 201
    return list(db.scalars(select(Alert.id).order_by(Alert.id)))


def _set(db: Session, alert_id: int, **values: Any) -> None:
    db.execute(update(Alert).where(Alert.id == alert_id).values(**values))


def test_workflow_metrics_on_seeded_alerts(
    client: TestClient, open_session: Any, post_event: Callable[..., Any], db: Session
) -> None:
    ids = _seed(db, post_event, 6)
    resolved = AlertStatus.RESOLVED
    # (created, acknowledged, resolved, outcome, status)
    rows = [
        (0, 60, 180, AlertOutcome.FALSE_ALARM, resolved),  # chờ 60, xử lý 120
        (10, 40, 100, AlertOutcome.CONFIRMED, resolved),  # chờ 30, xử lý 60
        (20, 110, 410, None, resolved),  # chờ 90, xử lý 300, chưa ghi kết quả
        (30, 50, None, None, AlertStatus.ACKNOWLEDGED),  # chờ 20
        (40, None, None, None, AlertStatus.PENDING),  # chưa tiếp nhận: không vào thời gian chờ
        (-3600, -3500, -3400, AlertOutcome.FALSE_ALARM, resolved),  # ngoài khoảng
    ]
    for alert_id, (c, a, r, outcome, status) in zip(ids, rows, strict=True):
        _set(
            db,
            alert_id,
            created_at=_s(c),
            acknowledged_at=None if a is None else _s(a),
            resolved_at=None if r is None else _s(r),
            outcome=outcome,
            status=status,
        )
    db.commit()

    m = workflow_metrics(db, T0, END)
    assert m.alerts == 5
    assert m.ack_samples == 4
    assert m.ack_wait_median_s == pytest.approx(45.0)
    assert m.ack_wait_p90_s == pytest.approx(81.0)
    assert m.resolve_samples == 3
    assert m.resolve_median_s == pytest.approx(120.0)
    assert m.resolve_p90_s == pytest.approx(264.0)
    assert m.resolved == 3
    assert m.resolved_with_outcome == 2
    assert m.outcome_rate == pytest.approx(2 / 3)
    assert m.with_outcome == 2
    assert m.false_alarm == 1
    assert m.false_alarm_rate == pytest.approx(0.5)
    assert m.pending_at_end == 1
    assert m.acknowledged_at_end == 1
    data = m.to_dict()
    assert data["alerts"] == 5 and data["from"] == T0.isoformat()


def test_workflow_status_at_end_of_range(
    client: TestClient, open_session: Any, post_event: Callable[..., Any], db: Session
) -> None:
    """Trạng thái "cuối khoảng" theo thời điểm, không theo trạng thái hiện tại."""
    [alert_id] = _seed(db, post_event, 1)
    _set(
        db,
        alert_id,
        created_at=_s(10),
        acknowledged_at=END + timedelta(minutes=5),
        resolved_at=None,
        status=AlertStatus.ACKNOWLEDGED,
    )
    db.commit()
    m = workflow_metrics(db, T0, END)
    assert m.pending_at_end == 1 and m.acknowledged_at_end == 0
    assert m.ack_samples == 1  # vẫn tính thời gian chờ của cảnh báo tạo trong khoảng


def test_workflow_metrics_empty_range(client: TestClient, db: Session) -> None:
    m = workflow_metrics(db, T0, END)
    assert m.alerts == 0
    assert m.ack_wait_median_s is None and m.resolve_p90_s is None
    assert m.outcome_rate is None and m.false_alarm_rate is None


def test_workflow_rejects_inverted_range(client: TestClient, db: Session) -> None:
    with pytest.raises(ValueError):
        workflow_metrics(db, END, T0)
