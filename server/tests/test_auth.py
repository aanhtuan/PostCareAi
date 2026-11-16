"""F02: đăng nhập, JWT, phân quyền theo vai trò (DOCTOR chỉ đọc), định dạng lỗi."""

from fastapi.testclient import TestClient

from tests.conftest import PASSWORD


def test_health(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_login_returns_token_and_user(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"username": "nurse", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "NURSE"
    assert "password_hash" not in body["user"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["username"] == "nurse"


def test_login_wrong_password_and_unknown_user_same_error(client: TestClient) -> None:
    for username, password in (("nurse", "sai"), ("khong-co", PASSWORD)):
        r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_missing_or_bad_token_is_401(client: TestClient) -> None:
    assert client.get("/api/v1/overview").json()["error"]["code"] == "UNAUTHORIZED"
    r = client.get("/api/v1/overview", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_validation_error_is_wrapped(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"username": "nurse"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_doctor_is_read_only(client: TestClient, login, open_session, post_event) -> None:
    doctor = login("doctor")
    # Đọc được mọi màn hình.
    for path in ("/api/v1/overview", "/api/v1/alerts", "/api/v1/events", "/api/v1/beds"):
        assert client.get(path, headers=doctor).status_code == 200, path
    # Không được ghi.
    alert_id = _make_alert(client, login, post_event)
    for path in (
        f"/api/v1/alerts/{alert_id}/acknowledge",
        f"/api/v1/sessions/{open_session['id']}/end",
    ):
        r = client.post(path, headers=doctor)
        assert r.status_code == 403, path
        assert r.json()["error"]["code"] == "FORBIDDEN"
    r = client.post("/api/v1/sessions", json={"bed_id": 2, "patient_id": 2}, headers=doctor)
    assert r.status_code == 403


def test_worker_endpoints_require_worker_token(client: TestClient, login) -> None:
    assert client.get("/internal/v1/cameras/1/config").status_code == 401
    r = client.get("/internal/v1/cameras/1/config", headers={"X-Worker-Token": "sai"})
    assert r.status_code == 401
    # JWT của người dùng không thay được worker token.
    assert client.get("/internal/v1/cameras/1/config", headers=login("admin")).status_code == 401


def _make_alert(client: TestClient, login, post_event) -> int:
    r = post_event("BED_EXIT", "HIGH")
    assert r.status_code == 201, r.text
    alerts = client.get("/api/v1/alerts", headers=login("nurse")).json()
    return alerts["items"][0]["id"]
