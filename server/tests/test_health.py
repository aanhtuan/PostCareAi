"""F00 AC2: endpoint health (R8)."""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_unknown_path_returns_404(client: TestClient) -> None:
    r = client.get("/api/v1/khong-ton-tai")
    assert r.status_code == 404


def test_health_is_served_by_v1_router() -> None:
    """R2/§4: endpoint nằm trong `postcare.api.v1.health` (router), không khai báo trong main."""
    from postcare.api.v1 import health

    paths = {getattr(route, "path", None) for route in health.router.routes}
    assert paths & {"/health", "/api/v1/health"}
