"""F03 AC1, AC2, AC4: bệnh nhân chỉ có mã thử nghiệm và ghi chú (PDF §10.1; HS §6.3)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog

PATIENTS = "/api/v1/patients"


def test_admin_crud_patients(client: TestClient, login, db: Session) -> None:
    admin = login("admin")
    r = client.post(PATIENTS, json={"code": "BN-100", "note": "Sau mổ ruột thừa"}, headers=admin)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["code"] == "BN-100" and p["note"] == "Sau mổ ruột thừa"
    assert p["is_active"] is True and p["active_session_id"] is None

    r = client.patch(f"{PATIENTS}/{p['id']}", json={"note": None}, headers=admin)
    assert r.status_code == 200 and r.json()["note"] is None
    r = client.get(f"{PATIENTS}/{p['id']}", headers=login("charge"))
    assert r.status_code == 200 and r.json()["code"] == "BN-100"

    db.expire_all()
    logs = list(
        db.scalars(select(AuditLog).where(AuditLog.entity_type == "patient").order_by(AuditLog.id))
    )
    assert [log.action for log in logs] == ["patient.create", "patient.update"]
    assert logs[1].before == {"code": "BN-100", "note": "Sau mổ ruột thừa", "is_active": True}
    assert logs[1].after == {"code": "BN-100", "note": None, "is_active": True}


def test_patient_list_paginated(client: TestClient, login) -> None:
    body = client.get(PATIENTS, params={"limit": 2}, headers=login("nurse")).json()
    assert body["total"] == 5
    assert [p["code"] for p in body["items"]] == ["BN-001", "BN-002"]


def test_duplicate_patient_code_409(client: TestClient, login) -> None:
    r = client.post(PATIENTS, json={"code": " BN-001 "}, headers=login("admin"))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "DUPLICATE_CODE"


@pytest.mark.parametrize("extra", [{"full_name": "Nguyễn Văn A"}, {"photo": "abc.jpg"}])
def test_patient_rejects_name_and_photo_fields(client: TestClient, login, extra: dict) -> None:
    admin = login("admin")
    r = client.post(PATIENTS, json={"code": "BN-200", **extra}, headers=admin)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    r = client.patch(f"{PATIENTS}/1", json=extra, headers=admin)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_patient_out_has_no_name_field(client: TestClient, login) -> None:
    allowed = {"id", "code", "note", "is_active", "active_session_id"}
    h = login("nurse")
    assert set(client.get(f"{PATIENTS}/1", headers=h).json()) == allowed
    for item in client.get(PATIENTS, headers=h).json()["items"]:
        assert set(item) == allowed
