"""F02 R8: định dạng lỗi chung `{error:{code,message,details}}` (api-conventions.md "Lỗi")."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from postcare.domain.errors import DomainError


def test_validation_error_format(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"username": "nurse"})
    assert r.status_code == 422
    body = r.json()
    assert set(body) == {"error"}
    err = body["error"]
    assert set(err) == {"code", "message", "details"}
    assert err["code"] == "VALIDATION_ERROR"
    assert err["message"] == "Dữ liệu không hợp lệ"
    assert ["body", "password"] in [e["loc"] for e in err["details"]["errors"]]


def test_domain_error_format(app: FastAPI, client: TestClient) -> None:
    @app.get("/api/v1/_test_domain_error")
    def boom() -> None:
        raise DomainError("SESSION_ALREADY_OPEN", "Giường đã có phiên", 409, {"bed_id": 1})

    r = client.get("/api/v1/_test_domain_error")
    assert r.status_code == 409
    assert r.json() == {
        "error": {
            "code": "SESSION_ALREADY_OPEN",
            "message": "Giường đã có phiên",
            "details": {"bed_id": 1},
        }
    }


def test_unknown_route_uses_common_format(client: TestClient) -> None:
    r = client.get("/api/v1/khong-co")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
