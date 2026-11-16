"""Handler lỗi chung: mọi lỗi trả `{error: {code, message, details}}` (api-conventions.md)."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from postcare.domain.errors import DomainError

_HTTP_CODES = {
    400: ("VALIDATION_ERROR", "Dữ liệu không hợp lệ"),
    401: ("UNAUTHORIZED", "Chưa đăng nhập hoặc phiên đăng nhập đã hết hạn"),
    403: ("FORBIDDEN", "Không đủ quyền thực hiện thao tác này"),
    404: ("NOT_FOUND", "Không tìm thấy dữ liệu"),
    405: ("METHOD_NOT_ALLOWED", "Phương thức không được hỗ trợ"),
}


def error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            error_body(exc.code, exc.message, exc.details), status_code=exc.http_status
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = {
            "errors": [
                {"loc": [str(p) for p in e.get("loc", [])], "msg": e.get("msg", "")}
                for e in exc.errors()
            ]
        }
        return JSONResponse(
            error_body("VALIDATION_ERROR", "Dữ liệu không hợp lệ", details), status_code=422
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _HTTP_CODES.get(exc.status_code, ("ERROR", "Có lỗi xảy ra"))
        return JSONResponse(
            error_body(code, message), status_code=exc.status_code, headers=exc.headers
        )
