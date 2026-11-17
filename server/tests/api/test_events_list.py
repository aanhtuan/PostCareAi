"""F17 R20: `GET /api/v1/events` (lọc, phân trang, sắp `occurred_at` giảm dần, quyền đọc)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from postcare.db.models import User
from postcare.domain.security import hash_password
from postcare.schemas.enums import UserRole
from tests.conftest import PASSWORD

T0 = datetime.now(UTC) + timedelta(hours=1)  # sau lúc mở phiên trong mọi test


@pytest.fixture
def seeded(client: TestClient, login: Any, open_session: dict[str, Any], post_event: Any) -> Any:
    """4 sự kiện giường A01 (phiên mở), cách nhau 10 s."""
    specs = [
        ("SIT_UP", "INFO"),
        ("BED_EDGE", "MEDIUM"),
        ("BED_EXIT", "HIGH"),
        ("POSTURE_CHANGE", "LOG"),
    ]
    ids = []
    for i, (code, priority) in enumerate(specs):
        r = post_event(code, priority, occurred_at=T0 + timedelta(seconds=10 * i))
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    return ids


def _get(client: TestClient, headers: dict[str, str], **params: Any) -> Any:
    r = client.get("/api/v1/events", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_list_sorted_desc_with_total(client: TestClient, login: Any, seeded: list[int]) -> None:
    data = _get(client, login("nurse"))
    assert data["total"] == 4
    assert [e["id"] for e in data["items"]] == list(reversed(seeded))


def test_filters(
    client: TestClient, login: Any, seeded: list[int], open_session: dict[str, Any]
) -> None:
    h = login("nurse")
    assert _get(client, h, bed_id=1)["total"] == 4
    assert _get(client, h, bed_id=2)["total"] == 0
    assert _get(client, h, session_id=open_session["id"])["total"] == 4
    assert _get(client, h, session_id=open_session["id"] + 99)["total"] == 0
    window = _get(
        client,
        h,
        **{
            "from": (T0 + timedelta(seconds=5)).isoformat(),
            "to": (T0 + timedelta(seconds=25)).isoformat(),
        },
    )
    assert [e["code"] for e in window["items"]] == ["BED_EXIT", "BED_EDGE"]
    r = client.get(
        "/api/v1/events", headers=h, params=[("priority", "HIGH"), ("priority", "MEDIUM")]
    )
    assert {e["code"] for e in r.json()["items"]} == {"BED_EXIT", "BED_EDGE"}
    assert [e["code"] for e in _get(client, h, code="SIT_UP")["items"]] == ["SIT_UP"]


def test_pagination(client: TestClient, login: Any, seeded: list[int]) -> None:
    h = login("nurse")
    page = _get(client, h, limit=2, offset=1)
    assert page["total"] == 4
    assert [e["id"] for e in page["items"]] == [seeded[2], seeded[1]]


@pytest.mark.parametrize(
    "params", [{"limit": 201}, {"limit": 0}, {"offset": -1}, {"priority": "X"}]
)
def test_bad_params_422(client: TestClient, login: Any, params: dict[str, Any]) -> None:
    """Lỗi schema của FastAPI → 422 `VALIDATION_ERROR` (api-conventions.md, mục Lỗi)."""
    r = client.get("/api/v1/events", headers=login("nurse"), params=params)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("username", ["nurse", "charge", "doctor", "admin"])
def test_staff_roles_can_read(
    client: TestClient, login: Any, seeded: list[int], username: str
) -> None:
    assert _get(client, login(username))["total"] == 4


def test_family_forbidden_and_unauthenticated_401(
    client: TestClient, login: Any, db: Session, seeded: list[int]
) -> None:
    db.add(
        User(
            username="family",
            full_name="Người nhà thử nghiệm",
            password_hash=hash_password(PASSWORD),
            role=UserRole.FAMILY,
        )
    )
    db.commit()
    r = client.get("/api/v1/events", headers=login("family"))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"
    assert client.get("/api/v1/events").status_code == 401


def test_event_out_carries_explanation_and_alert_status(
    client: TestClient, login: Any, seeded: list[int]
) -> None:
    items = {e["code"]: e for e in _get(client, login("doctor"))["items"]}
    assert items["BED_EXIT"]["explanation"] == {"rule_id": "test"}
    assert items["BED_EXIT"]["alert_status"] == "PENDING"
    assert items["SIT_UP"]["alert_status"] is None
