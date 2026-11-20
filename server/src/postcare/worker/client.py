"""HTTP client của worker tới API nội bộ `/internal/v1/*` (ADR-0002; api-conventions.md).

Nhận một `httpx.Client` được inject (F06 R12): chạy thật dùng `httpx.Client(base_url=…)`, test
dùng `httpx.MockTransport` hoặc `TestClient` của FastAPI.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

import httpx

from postcare.worker.config import WorkerConfig

logger = logging.getLogger(__name__)


class WorkerApiError(RuntimeError):
    """API trả lỗi 4xx không mong đợi."""


class ApiUnavailableError(WorkerApiError):
    """Lỗi mạng hoặc 5xx: tạm thời, thử lại sau (F06 R10)."""


class CameraNotFoundError(WorkerApiError):
    """404: camera không tồn tại hoặc đã ngừng dùng (giả định F06 §7: worker dừng)."""


class WorkerUnauthorizedError(WorkerApiError):
    """401: `WORKER_TOKEN` của worker khác của API."""


class EventResult(StrEnum):
    CREATED = "created"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    RETRY = "retry"


def _error_code(r: httpx.Response) -> str:
    try:
        return str(r.json()["error"]["code"])
    except (ValueError, KeyError, TypeError):
        return str(r.status_code)


class WorkerApiClient:
    def __init__(
        self,
        http: httpx.Client,
        *,
        camera_id: int,
        token: str,
        request_timeout_s: float = 3.0,
        heartbeat_timeout_s: float = 1.0,
    ) -> None:
        # Timeout ngắn: API treo không chặn vòng lặp worker lâu (heartbeat ngắn nhất).
        self.request_timeout_s = request_timeout_s
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self.http = http
        self.camera_id = camera_id
        self._headers = {"X-Worker-Token": token}
        self._base = f"/internal/v1/cameras/{camera_id}"

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**self._headers, **kwargs.pop("headers", {})}
        kwargs.setdefault("timeout", self.request_timeout_s)
        try:
            r = self.http.request(method, path, headers=headers, **kwargs)
        except httpx.TransportError as exc:
            raise ApiUnavailableError(f"API không phản hồi: {exc}") from exc
        if r.status_code >= 500:
            raise ApiUnavailableError(f"API lỗi {r.status_code} ({_error_code(r)})")
        if r.status_code == 401:
            raise WorkerUnauthorizedError("API từ chối WORKER_TOKEN (401)")
        return r

    def _camera_gone(self) -> CameraNotFoundError:
        return CameraNotFoundError(f"Camera {self.camera_id} không tồn tại hoặc đã ngừng dùng")

    def get_config(self) -> WorkerConfig:
        r = self._request("GET", f"{self._base}/config")
        if r.status_code == 404:
            raise self._camera_gone()
        if r.status_code != 200:
            raise WorkerApiError(f"GET config lỗi {r.status_code} ({_error_code(r)})")
        return WorkerConfig.model_validate(r.json())

    def heartbeat(self, body: dict[str, Any]) -> int:
        """Gửi heartbeat, trả `config_version` hiện tại trên API (A02)."""
        r = self._request(
            "POST", f"{self._base}/heartbeat", json=body, timeout=self.heartbeat_timeout_s
        )
        if r.status_code == 404:
            raise self._camera_gone()
        if r.status_code != 200:
            raise WorkerApiError(f"heartbeat lỗi {r.status_code} ({_error_code(r)})")
        return int(r.json()["config_version"])

    def post_frame(self, jpeg: bytes, *, config_version: int | None, view: str = "display") -> None:
        headers = {"Content-Type": "image/jpeg"}
        if config_version is not None:
            headers["X-Camera-Config-Version"] = str(config_version)
        kwargs: dict[str, Any] = {
            "content": jpeg,
            "headers": headers,
        }
        if view != "display":
            kwargs["params"] = {"view": view}
        r = self._request("POST", f"{self._base}/frame", **kwargs)
        if r.status_code != 204:
            raise WorkerApiError(f"frame lỗi {r.status_code} ({_error_code(r)})")

    def post_state(self, body: dict[str, Any]) -> None:
        r = self._request("POST", f"{self._base}/state", json=body)
        if r.status_code != 200:
            raise WorkerApiError(f"state lỗi {r.status_code} ({_error_code(r)})")

    def post_event(self, body: dict[str, Any]) -> EventResult:
        """201 → CREATED, 200 → DUPLICATE (idempotent), 409/4xx → REJECTED, mạng/5xx → RETRY."""
        try:
            r = self._request("POST", "/internal/v1/events", json=body)
        except ApiUnavailableError as exc:
            logger.warning("Gửi sự kiện %s thất bại, sẽ gửi lại: %s", body["code"], exc)
            return EventResult.RETRY
        if r.status_code == 201:
            return EventResult.CREATED
        if r.status_code == 200:
            return EventResult.DUPLICATE
        logger.warning(
            "API từ chối sự kiện %s (%s, %s): bỏ, không gửi lại",
            body["code"],
            r.status_code,
            _error_code(r),
        )
        return EventResult.REJECTED
