"""Tiện ích test worker (F06): API giả bằng `httpx.MockTransport`, đồng hồ giả, engine giả.

Không chờ thật: `FakeTime.sleep` chỉ cộng thời gian (R13).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from postcare.schemas.context import EngineContext
from postcare.schemas.enums import (
    ActivityLevel,
    BodyState,
    CameraStatus,
    FaceStatus,
    ObservationQuality,
    Priority,
    RestStatus,
)
from postcare.schemas.events import EngineEvent, EngineOutput, EventCode
from postcare.schemas.observation import FaceObservation, FrameObservation, PersonPose
from postcare.schemas.roi import validate_roi_polygon
from postcare.schemas.state import BodyStateSnapshot, FaceSignals
from postcare.vision.fake import FakeFrameSource
from postcare.vision.inference.face_gate import FaceGate
from postcare.vision.inference.fake import FakePoseAdapter
from postcare.worker.client import WorkerApiClient
from postcare.worker.config import WorkerConfig
from postcare.worker.loop import Worker, WorkerOptions

TOKEN = "worker-token-for-tests-at-least-32-bytes"
ROI = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.9], [0.2, 0.9]]
T0_UTC = datetime(2026, 11, 18, 3, 0, 0, tzinfo=UTC)


class FakeTime:
    """Đồng hồ đơn điệu (giây) + đồng hồ UTC đi cùng nhau; `sleep` chỉ cộng thời gian."""

    def __init__(self) -> None:
        self.t = 100.0
        self.slept = 0.0

    def monotonic(self) -> float:
        return self.t

    def wall(self) -> datetime:
        return T0_UTC + timedelta(seconds=self.t - 100.0)

    def sleep(self, seconds: float) -> None:
        self.t += max(seconds, 0.0)
        self.slept += max(seconds, 0.0)


def default_config(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "camera_id": 1,
        "bed_id": 1,
        "source_type": "FILE",
        "source": "fake.mp4",
        "roi_polygon": ROI,
        "thresholds": {},
        "display_mode": "RAW",
        "config_version": 1,
        "active_session_id": 7,
        "capture_paused": False,
    }
    cfg.update(overrides)
    return cfg


@dataclass
class FakeApi:
    """API nội bộ giả. Ghi lại mọi request; trả lời theo trạng thái có thể đổi trong test."""

    time: FakeTime
    config: dict[str, Any] = field(default_factory=default_config)
    down: bool = False
    config_status: int = 200
    event_statuses: list[int] = field(default_factory=list)
    """Mã trả lời lần lượt cho POST /events (hết danh sách → 201)."""
    calls: list[tuple[float, str, str, Any]] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("API không phản hồi", request=request)
        assert request.headers.get("X-Worker-Token") == TOKEN
        path = request.url.path
        body: Any = None
        if request.headers.get("content-type", "").startswith("application/json"):
            body = json.loads(request.content)
        elif request.content:
            body = request.content
        self.calls.append((self.time.t, request.method, path, body))
        if path.endswith("/config"):
            if self.config_status != 200:
                return httpx.Response(self.config_status, json=_error(self.config_status))
            return httpx.Response(200, json=self.config)
        if path.endswith("/heartbeat"):
            return httpx.Response(200, json={"config_version": self.config["config_version"]})
        if path.endswith("/frame"):
            return httpx.Response(204)
        if path.endswith("/state"):
            return httpx.Response(200, json={})
        if path == "/internal/v1/events":
            status = self.event_statuses.pop(0) if self.event_statuses else 201
            if status >= 400:
                return httpx.Response(status, json=_error(status))
            return httpx.Response(status, json={"id": 1, "created": status == 201})
        return httpx.Response(404, json=_error(404))

    def paths(self, suffix: str) -> list[tuple[float, str, str, Any]]:
        return [c for c in self.calls if c[2].endswith(suffix)]


def _error(status: int) -> dict[str, Any]:
    code = {
        401: "UNAUTHORIZED",
        404: "NOT_FOUND",
        409: "NO_ACTIVE_SESSION",
        500: "INTERNAL_ERROR",
        503: "INTERNAL_ERROR",
    }.get(status, "VALIDATION_ERROR")
    return {"error": {"code": code, "message": "test", "details": {}}}


def snapshot(body_state: BodyState = BodyState.LYING) -> BodyStateSnapshot:
    return BodyStateSnapshot(
        body_state=body_state,
        observation_quality=ObservationQuality.GOOD,
        activity_level=ActivityLevel.LOW,
        rest_status=RestStatus.UNKNOWN,
        face_status=FaceStatus.NOT_VISIBLE,
        face_signals=FaceSignals(),
    )


def engine_event(ts_ms: int, code: EventCode = EventCode.BED_EXIT) -> EngineEvent:
    return EngineEvent(
        code=code,
        priority=Priority.HIGH,
        occurred_at_ms=max(ts_ms - 500, 0),
        detected_at_ms=ts_ms,
        confidence=0.9,
        observation_quality=ObservationQuality.GOOD,
        explanation={"rule_id": "test.rule"},
        config_hash="hash-test",
    )


class FakeEngine:
    """Engine giả: trạng thái/sự kiện theo `frame_index` (kịch bản do test đặt)."""

    def __init__(
        self,
        context: EngineContext,
        *,
        states: dict[int, BodyState] | None = None,
        events_at: Iterable[int] = (),
    ) -> None:
        self.context = context
        self.config_hash = "hash-test"
        self._states = states or {}
        self._events_at = set(events_at)
        self._current = BodyState.LYING
        self.processed: list[int] = []
        self.faces: list[FaceObservation | None] = []

    def peek_target(self, obs: FrameObservation) -> PersonPose | None:
        """Mục tiêu giả: người đầu tiên trong khung (F25)."""
        return obs.persons[0] if obs.persons else None

    def process(self, obs: FrameObservation) -> EngineOutput:
        self.processed.append(obs.frame_index)
        self.faces.append(obs.face)
        changed = False
        if obs.frame_index in self._states:
            new = self._states[obs.frame_index]
            changed = new is not self._current
            self._current = new
        if obs.frame_index == 0:
            changed = True
        events = [engine_event(obs.ts_ms)] if obs.frame_index in self._events_at else []
        return EngineOutput(state=snapshot(self._current), state_changed=changed, events=events)


def frames_script(seconds: float, fps: float = 15.0) -> list[int | CameraStatus]:
    n = int(seconds * fps)
    return [round(i * 1000 / fps) for i in range(n)]


@dataclass
class Harness:
    api: FakeApi
    time: FakeTime
    worker: Worker
    engines: list[FakeEngine]
    sources: list[FakeFrameSource]
    adapters: list[FakePoseAdapter]

    def run_until(self, t_rel: float, *, max_steps: int = 100_000) -> None:
        """Chạy `step()` tới khi đồng hồ giả qua mốc `t_rel` giây kể từ lúc bắt đầu."""
        end = 100.0 + t_rel
        for _ in range(max_steps):
            if self.time.t >= end:
                return
            self.worker.step()
        raise AssertionError("worker không tiến thời gian (vòng lặp bận?)")


def make_harness(
    *,
    script: Callable[[], list[int | CameraStatus]] | None = None,
    engine_kwargs: dict[str, Any] | None = None,
    options: WorkerOptions | None = None,
    config: dict[str, Any] | None = None,
    source: Callable[[], Any] | None = None,
    pace: Callable[[Any], bool] | None = None,
    hang: bool = False,
    persons: Callable[[int], list[PersonPose]] | None = None,
    face_factory: Callable[[WorkerConfig], FaceGate | None] | None = None,
) -> Harness:
    t = FakeTime()
    api = FakeApi(time=t, config=config or default_config())
    handler = hanging_handler(api) if hang else api.handler
    http = httpx.Client(base_url="http://api.test", transport=httpx.MockTransport(handler))
    client = WorkerApiClient(http, camera_id=1, token=TOKEN)
    engines: list[FakeEngine] = []
    sources: list[FakeFrameSource] = []
    adapters: list[FakePoseAdapter] = []
    make_script = script or (lambda: frames_script(60))

    def engine_factory(cfg: WorkerConfig) -> FakeEngine:
        assert cfg.roi_polygon is not None
        ctx = EngineContext(
            camera_id=cfg.camera_id, roi_polygon=validate_roi_polygon(cfg.roi_polygon)
        )
        engine = FakeEngine(ctx, **(engine_kwargs or {}))
        engines.append(engine)
        return engine

    def source_factory(cfg: WorkerConfig) -> Any:
        src = source() if source is not None else FakeFrameSource(make_script())
        sources.append(src)
        return src

    def adapter_factory(cfg: WorkerConfig) -> FakePoseAdapter:
        by_index = {i: persons(i) for i in range(len(make_script()))} if persons else {}
        adapter = FakePoseAdapter(by_index)
        adapters.append(adapter)
        return adapter

    worker = Worker(
        client,
        engine_factory=engine_factory,
        source_factory=source_factory,
        adapter_factory=adapter_factory,
        face_factory=face_factory,
        options=options or WorkerOptions(),
        clock=t.monotonic,
        wall=t.wall,
        sleep=t.sleep,
        pace=pace or (lambda _src: True),
    )
    return Harness(api, t, worker, engines, sources, adapters)


def hanging_handler(api: FakeApi) -> Callable[[httpx.Request], httpx.Response]:
    """API treo khi `api.down`: mỗi request "chờ" hết timeout đọc (đồng hồ giả) rồi ReadTimeout."""

    def _handle(request: httpx.Request) -> httpx.Response:
        if api.down:
            timeout = request.extensions.get("timeout", {}).get("read") or 30.0
            api.time.t += min(float(timeout), 30.0)
            api.calls.append((api.time.t, request.method, request.url.path + "#timeout", None))
            raise httpx.ReadTimeout("API treo", request=request)
        return api.handler(request)

    return _handle
