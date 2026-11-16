"""F19 / ADR-0007: vòng đời cảnh báo, 1 người tiếp nhận, chuyển trạng thái sai, audit."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog
from postcare.domain.notifications import InMemoryPublisher


def _alert_id(client: TestClient, login, post_event, code="BED_EXIT", prio="HIGH") -> int:
    assert post_event(code, prio).status_code == 201
    items = client.get("/api/v1/alerts", headers=login("nurse")).json()["items"]
    return max(i["id"] for i in items)


def test_full_lifecycle(
    client: TestClient,
    login,
    open_session,
    post_event,
    db: Session,
    publisher: InMemoryPublisher,
) -> None:
    nurse, charge = login("nurse"), login("charge")
    aid = _alert_id(client, login, post_event)
    publisher.messages.clear()

    r = client.post(f"/api/v1/alerts/{aid}/acknowledge", headers=nurse)
    assert r.status_code == 200
    a = r.json()
    assert a["status"] == "ACKNOWLEDGED"
    assert a["acknowledged_by"]["full_name"] == "Nguyễn Thị Hoa"

    r = client.post(f"/api/v1/alerts/{aid}/outcome", json={"outcome": "CONFIRMED"}, headers=charge)
    assert r.status_code == 200 and r.json()["outcome"] == "CONFIRMED"
    # Ghi lại kết quả: ghi đè, người ghi lưu riêng.
    r = client.post(
        f"/api/v1/alerts/{aid}/outcome",
        json={"outcome": "PATIENT_SAFE", "note": "Đã hỗ trợ về giường"},
        headers=nurse,
    )
    assert r.json()["outcome"] == "PATIENT_SAFE"
    assert r.json()["note"] == "Đã hỗ trợ về giường"

    r = client.post(f"/api/v1/alerts/{aid}/resolve", json={}, headers=charge)
    assert r.status_code == 200
    a = r.json()
    assert a["status"] == "RESOLVED"
    assert a["resolved_by"]["full_name"] == "Trần Văn Minh"
    assert a["acknowledged_by"]["full_name"] == "Nguyễn Thị Hoa"

    actions = [
        log.action
        for log in db.scalars(
            select(AuditLog).where(AuditLog.entity_type == "alert").order_by(AuditLog.id)
        )
    ]
    assert actions == [
        "alert.create",
        "alert.acknowledge",
        "alert.outcome",
        "alert.outcome",
        "alert.resolve",
    ]
    assert publisher.types() == ["alert.updated"] * 4


def test_second_acknowledge_is_409_with_name(
    client: TestClient,
    login,
    open_session,
    post_event,
    publisher: InMemoryPublisher,
) -> None:
    aid = _alert_id(client, login, post_event)
    assert (
        client.post(f"/api/v1/alerts/{aid}/acknowledge", headers=login("nurse")).status_code == 200
    )
    publisher.messages.clear()
    for who in ("charge", "nurse"):
        r = client.post(f"/api/v1/alerts/{aid}/acknowledge", headers=login(who))
        assert r.status_code == 409
        err = r.json()["error"]
        assert err["code"] == "ALERT_ALREADY_ACKNOWLEDGED"
        assert "Nguyễn Thị Hoa" in err["message"]
        assert err["details"]["acknowledged_by"]["full_name"] == "Nguyễn Thị Hoa"
    assert publisher.messages == []  # 409 không phát thông báo


def test_invalid_transitions(client: TestClient, login, open_session, post_event) -> None:
    nurse = login("nurse")
    aid = _alert_id(client, login, post_event)

    def code(r) -> str:
        assert r.status_code == 409, r.text
        return r.json()["error"]["code"]

    # PENDING: chưa được ghi kết quả hay xử lý.
    assert code(client.post(f"/api/v1/alerts/{aid}/resolve", headers=nurse)) == (
        "INVALID_ALERT_TRANSITION"
    )
    assert (
        code(
            client.post(
                f"/api/v1/alerts/{aid}/outcome", json={"outcome": "FALSE_ALARM"}, headers=nurse
            )
        )
        == "INVALID_ALERT_TRANSITION"
    )

    client.post(f"/api/v1/alerts/{aid}/acknowledge", headers=nurse)
    # Xử lý khi chưa ghi kết quả là được phép (ADR-0007).
    r = client.post(f"/api/v1/alerts/{aid}/resolve", headers=nurse)
    assert r.status_code == 200 and r.json()["outcome"] is None

    # RESOLVED: không đi lùi.
    assert code(client.post(f"/api/v1/alerts/{aid}/acknowledge", headers=nurse)) == (
        "INVALID_ALERT_TRANSITION"
    )
    assert (
        code(
            client.post(
                f"/api/v1/alerts/{aid}/outcome", json={"outcome": "CONFIRMED"}, headers=nurse
            )
        )
        == "INVALID_ALERT_TRANSITION"
    )
    assert code(client.post(f"/api/v1/alerts/{aid}/resolve", headers=nurse)) == (
        "INVALID_ALERT_TRANSITION"
    )


def test_bad_outcome_and_unknown_alert(client: TestClient, login, open_session, post_event) -> None:
    nurse = login("nurse")
    aid = _alert_id(client, login, post_event)
    client.post(f"/api/v1/alerts/{aid}/acknowledge", headers=nurse)
    r = client.post(f"/api/v1/alerts/{aid}/outcome", json={"outcome": "PAIN"}, headers=nurse)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    r = client.post("/api/v1/alerts/9999/acknowledge", headers=nurse)
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_list_puts_unresolved_first(client: TestClient, login, open_session, post_event) -> None:
    nurse = login("nurse")
    a1 = _alert_id(client, login, post_event, "BED_EDGE", "MEDIUM")
    a2 = _alert_id(client, login, post_event, "BED_EXIT", "HIGH")
    a3 = _alert_id(client, login, post_event, "ABNORMAL_MOVEMENT", "HIGH")
    client.post(f"/api/v1/alerts/{a3}/acknowledge", headers=nurse)
    client.post(f"/api/v1/alerts/{a3}/resolve", headers=nurse)
    client.post(f"/api/v1/alerts/{a1}/acknowledge", headers=nurse)
    items = client.get("/api/v1/alerts", headers=nurse).json()["items"]
    assert [i["id"] for i in items] == [a2, a1, a3]
    pending = client.get("/api/v1/alerts?status=PENDING", headers=nurse).json()
    assert [i["id"] for i in pending["items"]] == [a2]
    high = client.get("/api/v1/alerts?priority=HIGH", headers=nurse).json()
    assert {i["id"] for i in high["items"]} == {a2, a3}
