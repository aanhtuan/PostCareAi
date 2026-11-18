"""Khởi tạo ứng dụng FastAPI. Chạy: `uvicorn postcare.api.main:app`."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from postcare.api.errors import install_error_handlers
from postcare.api.frame_buffer import LatestFrameStore
from postcare.api.internal import cameras as internal_cameras
from postcare.api.log_redaction import install_access_log_redaction
from postcare.api.realtime import WsHub
from postcare.api.realtime import router as ws_router
from postcare.api.v1 import (
    alerts,
    areas,
    auth,
    beds,
    cameras,
    catalog,
    health,
    monitoring,
    patients,
    sessions,
    stream,
    users,
)
from postcare.db.session import make_engine, make_session_factory
from postcare.domain.cameras import mark_offline_cameras
from postcare.domain.runtime import RuntimeStore
from postcare.settings import Settings, get_settings

logger = logging.getLogger(__name__)


async def _watch_cameras(app: FastAPI) -> None:
    """Định kỳ đánh dấu camera mất heartbeat là OFFLINE (A02)."""
    settings: Settings = app.state.settings

    def _tick() -> None:
        db = app.state.session_factory()
        try:
            mark_offline_cameras(
                db,
                app.state.store,
                app.state.hub,
                offline_after_s=settings.camera_offline_after_s,
            )
        finally:
            db.close()

    while True:
        await asyncio.sleep(settings.camera_watch_interval_s)
        try:
            await asyncio.to_thread(_tick)
        except Exception:
            logger.exception("Lỗi khi kiểm tra trạng thái camera")


def create_app(settings: Settings | None = None, *, watch_cameras: bool = True) -> FastAPI:
    settings = settings or get_settings()
    install_access_log_redaction()  # `?token=` của MJPEG/WS không vào access log
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Kiểm tra lúc khởi động, không lúc import: sinh OpenAPI (import module) vẫn chạy.
        settings.ensure_secure_secrets()
        # Schema do Alembic tạo (`make db-upgrade`), API không tự tạo bảng (F01).
        app.state.hub.bind_loop(asyncio.get_running_loop())
        task = asyncio.create_task(_watch_cameras(app)) if watch_cameras else None
        yield
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(
        title="PostCare AI API",
        version="0.1.0",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.store = RuntimeStore()
    app.state.frames = LatestFrameStore()  # F06: khung JPEG mới nhất, chỉ trong RAM
    app.state.hub = WsHub()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.web_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)

    v1_routers = (
        health.router,
        auth.router,
        catalog.router,
        areas.router,
        beds.router,
        patients.router,
        cameras.router,
        sessions.router,
        alerts.router,
        monitoring.router,
        users.router,
        stream.router,
    )
    for r in v1_routers:
        app.include_router(r, prefix="/api/v1")
    app.include_router(internal_cameras.router)
    app.include_router(ws_router)
    return app


app = create_app()
