"""Lỗi nghiệp vụ; handler ở `postcare.api.errors` chuyển thành `{error:{code,message,details}}`."""

from typing import Any


class DomainError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


def not_found(message: str = "Không tìm thấy dữ liệu") -> DomainError:
    return DomainError("NOT_FOUND", message, 404)


def validation_error(message: str, details: dict[str, Any] | None = None) -> DomainError:
    return DomainError("VALIDATION_ERROR", message, 400, details)
