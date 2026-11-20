"""Vòng lặp worker cho một camera (F06; kéo trước F17 R3–R7 phía worker, F36 R18 phía worker).

Một luồng, chạy theo `step()`; đồng hồ, hàm chờ, HTTP client, nguồn, adapter, engine đều inject để
test chạy nhanh và xác định (R12, R13). Mỗi `step()`:

1. Chưa có cấu hình → `GET config` (API sập: backoff 1 → 10 s, không thoát).
2. Đến hạn → heartbeat (2 s, A02); `config_version` khác → tải lại cấu hình. Poll cấu hình 5 s.
3. Gửi lại sự kiện đang chờ (cùng `event_uid`).
4. Tạm dừng thu hình → đóng nguồn, dừng engine, chỉ heartbeat (`source_status = PAUSED`).
5. Đọc một khung → `process_frame` (pose + face nếu `face.enabled` + engine) → state khi đổi,
   sự kiện; JPEG ~5 fps (A03). Nhánh face (F25) lỗi không làm dừng pose/engine (F25 R8).
   Khung được render theo `display_mode` (F28: RAW / BLUR / SKELETON) **trước** khi nén JPEG,
   nên ảnh gốc không rời tiến trình ở chế độ SKELETON. Chế độ hiển thị không ảnh hưởng engine.

Nguồn file được phát theo nhịp thời gian thực (`pace`): một camera không chạy nhanh hơn thời gian
thật. Quy đổi `ts_ms` → UTC: `t0_utc + (ts_ms − ts0_ms)` với `t0_utc` lúc nhận khung đầu (F17 R4).
Không ghi khung hình ra đĩa (QA#29).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from postcare.engine import Engine
from postcare.pipeline import FrameEngine, process_frame
from postcare.schemas.context import EngineContext
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.enums import DisplayMode, ObservationProfile
from postcare.schemas.events import EngineEvent, EngineOutput, EventCode
from postcare.schemas.observation import PersonPose
from postcare.schemas.roi import RoiPolygon, validate_roi_polygon
from postcare.schemas.state import BodyStateSnapshot
from postcare.vision.camera import FileSource, Frame, FrameSource, SourceOpenError
from postcare.vision.image_stats import mean_brightness
from postcare.vision.inference.base import PoseAdapter
from postcare.vision.inference.face_gate import FaceGate
from postcare.vision.render import PrivacyRenderer, encode_jpeg
from postcare.worker.client import (
    ApiUnavailableError,
    CameraNotFoundError,
    EventResult,
    WorkerApiClient,
    WorkerApiError,
    WorkerUnauthorizedError,
)
from postcare.worker.config import WorkerConfig, mask_source

logger = logging.getLogger(__name__)

PAUSED = "PAUSED"
OFFLINE = "OFFLINE"


class WorkerStopError(RuntimeError):
    """Lỗi không tự hết: camera không tồn tại/ngừng dùng (404) hoặc sai WORKER_TOKEN (401)."""


@dataclass(frozen=True)
class WorkerOptions:
    """Chu kỳ và giới hạn của worker (A02, A03, ADR-0002); CLI lấy từ `Settings`."""

    heartbeat_interval_s: float = 2.0
    config_poll_s: float = 5.0
    frame_fps: float = 5.0
    state_refresh_s: float = 5.0
    """Gửi lại trạng thái hiện tại định kỳ để API khởi động lại vẫn có trạng thái (giả định)."""
    source_retry_s: float = 2.0
    retry_initial_s: float = 1.0
    retry_max_s: float = 10.0
    event_queue_max: int = 200
    """Hàng đợi gửi lại sự kiện trong RAM (F17 R5); đầy thì bỏ sự kiện cũ nhất."""
    jpeg_max_side: int = 960
    jpeg_quality: int = 70
    read_timeout_s: float = 0.2
    idle_s: float = 0.1
    max_wait_s: float = 0.5
    """Mỗi lần chờ không quá giá trị này để Ctrl+C phản hồi nhanh."""
    loop: bool = False
    """Phát lại nguồn file từ đầu khi hết (`--loop`, dùng cho demo). Engine tạo mới mỗi vòng."""
    source_overridden: bool = False
    """Worker dùng `--video` thay cho nguồn đã lưu của camera."""


@dataclass
class _PendingEvent:
    body: dict[str, Any]
    next_try: float
    attempts: int = 0


EngineFactory = Callable[[WorkerConfig], FrameEngine]
SourceFactory = Callable[[WorkerConfig], FrameSource]
AdapterFactory = Callable[[WorkerConfig], PoseAdapter]
FaceFactory = Callable[[WorkerConfig], FaceGate | None]


def default_engine_factory(engine_config_path: Path | str) -> EngineFactory:
    """`Engine` thật: ngưỡng mặc định hợp nhất với `thresholds` của camera, ROI của camera."""

    def _make(cfg: WorkerConfig) -> FrameEngine:
        # shortcut: no-ROI profiles use full-frame ROI until multi-person targeting.
        roi = (
            cfg.roi_polygon
            if cfg.observation_profile == ObservationProfile.BED_MONITORING
            else None
        ) or [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        config = EngineConfig.load(engine_config_path, cfg.thresholds)
        context = EngineContext(camera_id=cfg.camera_id, roi_polygon=validate_roi_polygon(roi))
        return Engine(config, context)

    return _make


def default_face_factory(engine_config_path: Path | str, models_dir: Path) -> FaceFactory:
    """Cổng face thật (F25) theo `face.enabled` sau khi hợp nhất `thresholds` của camera.

    Tắt → `None`. Thiếu model face → cổng không adapter (luôn `NOT_VISIBLE`, WARNING; R8).
    """

    def _make(cfg: WorkerConfig) -> FaceGate | None:
        config = EngineConfig.load(engine_config_path, cfg.thresholds)
        if not config.face.enabled:
            return None
        # Nhập muộn: chỉ nạp mediapipe khi thật sự bật face (test worker không cần mediapipe).
        from postcare.settings import REPO_ROOT
        from postcare.vision.inference.face_landmarker import open_face_adapter
        from postcare.vision.models import load_manifest

        entry = load_manifest(REPO_ROOT / "config" / "models.yaml").face
        detector = None
        if entry is None:
            logger.warning("Manifest model không có face: nhánh face luôn NOT_VISIBLE")
        else:
            detector = open_face_adapter(models_dir / entry.filename, config)
        return FaceGate.from_config(config, detector)

    return _make


def default_renderer(engine_config_path: Path | str | None = None) -> PrivacyRenderer:
    """Bộ render theo `privacy.*` của cấu hình mặc định (không override theo camera, F08)."""
    if engine_config_path is None:
        from postcare.settings import REPO_ROOT

        engine_config_path = REPO_ROOT / "config" / "engine.default.yaml"
    return PrivacyRenderer.from_config(EngineConfig.load(engine_config_path))


def _is_file_source(source: FrameSource) -> bool:
    return isinstance(source, FileSource)


def _state_body(state: BodyStateSnapshot, ts: datetime) -> dict[str, Any]:
    return {
        "body_state": state.body_state.value,
        "observation_quality": state.observation_quality.value,
        "activity_level": state.activity_level.value,
        "rest_status": state.rest_status.value,
        "face_status": state.face_status.value,
        "face_signals": state.face_signals.model_dump(),
        "ts": ts.isoformat(),
    }


class Worker:
    def __init__(
        self,
        api: WorkerApiClient,
        *,
        engine_factory: EngineFactory,
        source_factory: SourceFactory,
        adapter_factory: AdapterFactory,
        face_factory: FaceFactory | None = None,
        renderer: PrivacyRenderer | None = None,
        options: WorkerOptions | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Any] = time.sleep,
        pace: Callable[[FrameSource], bool] = _is_file_source,
    ) -> None:
        self.api = api
        self.options = options or WorkerOptions()
        self._engine_factory = engine_factory
        self._source_factory = source_factory
        self._adapter_factory = adapter_factory
        self._face_factory = face_factory
        self.renderer = renderer or default_renderer()
        self._clock = clock
        self._wall = wall
        self._sleep = sleep
        self._pace = pace

        self.config: WorkerConfig | None = None
        self.source: FrameSource | None = None
        self.adapter: PoseAdapter | None = None
        self.engine: FrameEngine | None = None
        self.face: FaceGate | None = None
        """Cổng face (F25), tạo cùng engine; `None` khi tắt face hoặc tạo lỗi."""
        self._engine_key: tuple[Any, ...] | None = None
        self._engine_failed_key: tuple[Any, ...] | None = None
        self._persons: Sequence[PersonPose] = ()
        """Người pose phát hiện ở khung vừa xử lý: dùng để render BLUR / SKELETON (F28)."""
        self._roi_cache: tuple[str, RoiPolygon | None] | None = None

        self._config_retry_at = 0.0
        self._config_backoff = self.options.retry_initial_s
        self._next_heartbeat = 0.0
        self._next_poll = 0.0
        self._api_down_until = 0.0
        self._api_backoff = self.options.retry_initial_s
        self._api_reachable: bool | None = None
        self._source_retry_at = 0.0
        self._source_failed = False

        self._ts0_ms: int | None = None
        self._t0_utc: datetime | None = None
        self._play_t0 = 0.0
        self._brightness: float | None = None
        self._next_frame_at: float | None = None
        self._state_sent = False
        self._last_state_at = 0.0
        self._events: deque[_PendingEvent] = deque()

    # ---- thông tin cho test / log ----
    @property
    def pending_events(self) -> int:
        return len(self._events)

    @property
    def source_status(self) -> str:
        if self.config is not None and self.config.capture_paused:
            return PAUSED
        if self.source is None or self.source.ended:
            return OFFLINE
        return self.source.status.value

    # ---- vòng lặp ----
    def run(self, should_stop: Callable[[], bool] = lambda: False) -> None:
        while not should_stop():
            self.step()

    def step(self) -> None:
        now = self._clock()
        if self.config is None:
            if now < self._config_retry_at:
                self._wait_until(self._config_retry_at)
                return
            if not self._load_config(now):
                return
        cfg = self.config
        assert cfg is not None
        if not cfg.capture_paused:
            # Mở nguồn trước heartbeat đầu: không báo OFFLINE giả rồi ONLINE (sinh CAMERA_ONLINE).
            self._ensure_source(self._clock())
        now = self._clock()
        if now >= self._next_heartbeat:
            self._heartbeat(now)
        if now >= self._next_poll and self._api_open(self._clock()):
            self._load_config(now)
        self._flush_events(self._clock())
        cfg = self.config
        if cfg.capture_paused:
            if self.source is not None:
                logger.info("Phiên đang tạm dừng thu hình: dừng đọc khung, chỉ gửi heartbeat")
                self._close_source()
            self._wait_until(min(self._next_heartbeat, self._next_poll))
            return
        if not self._ensure_source(self._clock()):
            self._wait_until(min(self._next_heartbeat, self._next_poll, self._source_retry_at))
            return
        assert self.source is not None
        if self.source.ended:
            if self.options.loop:
                logger.info("Hết video, phát lại từ đầu (--loop)")
                self._close_source()
                return
            self._wait_until(min(self._next_heartbeat, self._next_poll))
            return
        frame = self.source.read(timeout_s=self.options.read_timeout_s)
        if frame is None:
            self._sleep(self.options.idle_s)
            return
        self._handle_frame(frame)

    def close(self) -> None:
        self._close_source()

    # ---- cấu hình ----
    def _load_config(self, now: float) -> bool:
        try:
            cfg = self.api.get_config()
        except (CameraNotFoundError, WorkerUnauthorizedError) as exc:
            raise WorkerStopError(str(exc)) from exc
        except WorkerApiError as exc:
            self._mark_api_error(now, exc)
            if self.config is None:
                self._config_retry_at = now + self._config_backoff
                self._config_backoff = min(self._config_backoff * 2, self.options.retry_max_s)
            else:
                self._next_poll = now + self.options.config_poll_s
            return False
        self._mark_api_ok()
        self._config_backoff = self.options.retry_initial_s
        self._next_poll = now + self.options.config_poll_s
        self._apply_config(cfg)
        return True

    def _apply_config(self, cfg: WorkerConfig) -> None:
        old = self.config
        self.config = cfg
        if old is None:
            logger.info(
                "Cấu hình camera %s: nguồn %s %s, phiên %s, config_version %s",
                cfg.camera_id,
                cfg.source_type.value,
                mask_source(cfg.source),
                cfg.active_session_id,
                cfg.config_version,
            )
            return
        if old.source_key != cfg.source_key:
            logger.info(
                "Nguồn đổi %s %s → %s %s: mở lại nguồn",
                old.source_type.value,
                mask_source(old.source),
                cfg.source_type.value,
                mask_source(cfg.source),
            )
            self._close_source()
        if old.engine_key != cfg.engine_key:
            logger.info(
                "Cấu hình mới (config_version %s, phiên %s): tạo engine mới",
                cfg.config_version,
                cfg.active_session_id,
            )
            self._reset_engine()
        if old.display_mode is not cfg.display_mode:
            logger.info("Chế độ hiển thị %s → %s", old.display_mode.value, cfg.display_mode.value)
        if old.capture_paused and not cfg.capture_paused:
            logger.info("Tiếp tục thu hình")

    # ---- heartbeat ----
    def _heartbeat(self, now: float) -> None:
        self._next_heartbeat = now + self.options.heartbeat_interval_s
        stats = self.source.stats if self.source is not None else None
        body = {
            "fps": round(stats.fps, 2) if stats else 0.0,
            "brightness": round(self._brightness, 1) if self._brightness is not None else None,
            "dropped_frames": stats.dropped_frames if stats else 0,
            "source_status": self.source_status,
        }
        try:
            version = self.api.heartbeat(body)
        except (CameraNotFoundError, WorkerUnauthorizedError) as exc:
            raise WorkerStopError(str(exc)) from exc
        except WorkerApiError as exc:
            self._mark_api_error(now, exc)
            return
        self._mark_api_ok()
        if self.config is not None and version != self.config.config_version:
            self._load_config(now)

    def _mark_api_error(self, now: float, exc: Exception) -> None:
        now = max(now, self._clock())  # request treo tới timeout: tính backoff từ lúc kết thúc
        if self._api_reachable is not False:
            logger.warning("Không gửi được tới API (%s); vẫn chạy và thử lại", exc)
        self._api_reachable = False
        if isinstance(exc, ApiUnavailableError):
            self._api_down_until = now + self._api_backoff
            self._api_backoff = min(self._api_backoff * 2, self.options.retry_max_s)

    def _mark_api_ok(self) -> None:
        if self._api_reachable is False:
            logger.info("Đã kết nối lại API")
        self._api_reachable = True
        self._api_down_until = 0.0
        self._api_backoff = self.options.retry_initial_s

    def _api_open(self, now: float) -> bool:
        return now >= self._api_down_until

    # ---- nguồn, adapter, engine ----
    def _ensure_source(self, now: float) -> bool:
        if self.source is not None:
            return True
        if now < self._source_retry_at:
            return False
        assert self.config is not None
        try:
            source = self._source_factory(self.config)
            source.open()
        except (SourceOpenError, ValueError, OSError) as exc:
            if not self._source_failed:
                logger.warning("Không mở được nguồn video: %s (thử lại sau)", exc)
            self._source_failed = True
            self._source_retry_at = now + self.options.source_retry_s
            return False
        if self._source_failed:
            logger.info("Đã mở lại nguồn video")
        self._source_failed = False
        self.source = source
        self.adapter = self._adapter_factory(self.config)
        self._ts0_ms = None
        self._next_frame_at = None
        self._reset_engine()
        return True

    def _close_source(self) -> None:
        if self.source is not None:
            self.source.close()
            self.source = None
        if self.adapter is not None:
            # MediaPipe VIDEO cần ts_ms tăng ngặt; nguồn mới bắt đầu lại ts nên cần adapter mới.
            self.adapter.close()
            self.adapter = None
        self._ts0_ms = None
        self._persons = ()
        self.renderer.reset()
        self._reset_engine()

    def _reset_engine(self) -> None:
        self.engine = None
        if self.face is not None:
            # Face Landmarker VIDEO cần ts_ms tăng ngặt: engine/nguồn mới → cổng face mới.
            self.face.close()
            self.face = None
        self._engine_key = None
        self._state_sent = False

    def _ensure_engine(self) -> FrameEngine | None:
        cfg = self.config
        assert cfg is not None
        if self.engine is not None and self._engine_key == cfg.engine_key:
            return self.engine
        if cfg.roi_polygon is None and cfg.observation_profile == ObservationProfile.BED_MONITORING:
            if self._engine_failed_key != cfg.engine_key:
                logger.warning("Camera chưa có ROI giường: chỉ gửi heartbeat và khung hình")
                self._engine_failed_key = cfg.engine_key
            return None
        try:
            engine = self._engine_factory(cfg)
        except ValueError as exc:
            if self._engine_failed_key != cfg.engine_key:
                logger.error("Cấu hình engine không hợp lệ: %s", exc)
                self._engine_failed_key = cfg.engine_key
            return None
        self.engine = engine
        self._engine_key = cfg.engine_key
        self._state_sent = False
        self.face = self._make_face(cfg)
        return engine

    def _make_face(self, cfg: WorkerConfig) -> FaceGate | None:
        if self._face_factory is None:
            return None
        try:
            return self._face_factory(cfg)
        except Exception as exc:  # F25 R8: face lỗi → chạy tiếp không có face
            logger.warning("Không tạo được nhánh face (%s): chỉ chạy pose + engine", exc)
            return None

    # ---- xử lý khung ----
    def _to_utc(self, ts_ms: int) -> datetime:
        assert self._t0_utc is not None and self._ts0_ms is not None
        return self._t0_utc + timedelta(milliseconds=ts_ms - self._ts0_ms)

    def _handle_frame(self, frame: Frame) -> None:
        assert self.source is not None and self.adapter is not None
        if self._ts0_ms is None:
            self._ts0_ms = frame.ts_ms
            self._t0_utc = self._wall()
            self._play_t0 = self._clock()
        elif self._pace(self.source):
            target = self._play_t0 + (frame.ts_ms - self._ts0_ms) / 1000.0
            delay = target - self._clock()
            if delay > 0:
                self._sleep(delay)
        self._brightness = mean_brightness(frame.image)
        engine = self._ensure_engine()
        if engine is not None:
            obs, output = process_frame(frame, self.adapter, engine, self.face)
            self._persons = obs.persons
            self._handle_output(frame, output)
        else:
            # Chưa có ROI: vẫn đo pose để khung skeleton hữu ích, nhưng không chạy engine.
            # Không gửi state/event vì chưa đủ cấu hình vùng giường để kết luận theo dõi.
            self._persons = self.adapter.observe(frame, self.config.camera_id).persons
        self._maybe_send_frame(frame, self._clock())

    def _handle_output(self, frame: Frame, output: EngineOutput) -> None:
        cfg = self.config
        assert cfg is not None
        now = self._clock()
        for event in output.events:
            if (
                cfg.observation_profile == ObservationProfile.ABNORMAL_MOVEMENT
                and event.code != EventCode.ABNORMAL_MOVEMENT
            ):
                continue
            if (
                cfg.observation_profile == ObservationProfile.FACE_SIGNALS
                and event.code != EventCode.FACE_ATTENTION
            ):
                continue
            if (
                cfg.active_session_id is None
                and cfg.observation_profile == ObservationProfile.BED_MONITORING
            ):
                # Giường không có phiên mở: không gửi sự kiện engine (F17 R6).
                continue
            self._enqueue(self._event_body(cfg, event))
        if self._events:
            self._flush_events(now)
        due_refresh = now - self._last_state_at >= self.options.state_refresh_s
        if output.state_changed or not self._state_sent or due_refresh:
            self._send_state(output.state, self._to_utc(frame.ts_ms), now)

    def _send_state(self, state: BodyStateSnapshot, ts: datetime, now: float) -> None:
        if not self._api_open(now):
            return
        try:
            self.api.post_state(_state_body(state, ts))
        except WorkerUnauthorizedError as exc:
            raise WorkerStopError(str(exc)) from exc
        except WorkerApiError as exc:
            self._mark_api_error(now, exc)
            self._state_sent = False  # gửi lại ở khung sau
            return
        self._state_sent = True
        self._last_state_at = now

    def _maybe_send_frame(self, frame: Frame, now: float) -> None:
        period = 1.0 / self.options.frame_fps
        if self._next_frame_at is not None and now < self._next_frame_at:
            return
        # Hạn cố định: trễ vài ms không làm tụt nhịp; trễ quá một chu kỳ thì đồng bộ lại.
        if self._next_frame_at is None or now - self._next_frame_at > period:
            self._next_frame_at = now + period
        else:
            self._next_frame_at += period
        if not self._api_open(now):
            return
        cfg = self.config
        assert cfg is not None
        # Render trong worker trước khi gửi (F28 R4): API/MJPEG chỉ chuyển tiếp JPEG này.
        try:
            image = self.renderer.render(
                frame.image,
                self._persons,
                ts_ms=frame.ts_ms,
                mode=cfg.display_mode,
                roi=self._roi(cfg),
            )
            jpeg = encode_jpeg(
                image, max_side=self.options.jpeg_max_side, quality=self.options.jpeg_quality
            )
        except Exception as exc:
            # Render/nén lỗi: bỏ khung này, không bao giờ gửi ảnh gốc thay thế; engine chạy tiếp.
            logger.warning("Không render được khung (%s): bỏ khung, không gửi", exc)
            return
        try:
            skeleton = encode_jpeg(
                self.renderer.render(
                    frame.image,
                    self._persons,
                    ts_ms=frame.ts_ms,
                    mode=DisplayMode.SKELETON,
                    roi=self._roi(cfg),
                ),
                max_side=self.options.jpeg_max_side,
                quality=self.options.jpeg_quality,
            )
            version = None if self.options.source_overridden else cfg.config_version
            self.api.post_frame(jpeg, config_version=version)
            self.api.post_frame(skeleton, config_version=version, view="skeleton")
        except WorkerUnauthorizedError as exc:
            raise WorkerStopError(str(exc)) from exc
        except WorkerApiError as exc:
            self._mark_api_error(now, exc)

    def _roi(self, cfg: WorkerConfig) -> RoiPolygon | None:
        """Bed ROI để vẽ ở chế độ SKELETON; ROI không hợp lệ → không vẽ."""
        polygon = (
            cfg.roi_polygon
            if cfg.observation_profile == ObservationProfile.BED_MONITORING
            else None
        )
        key = repr(polygon)
        if self._roi_cache is None or self._roi_cache[0] != key:
            roi: RoiPolygon | None = None
            if polygon is not None:
                try:
                    roi = validate_roi_polygon(polygon)
                except ValueError:
                    roi = None
            self._roi_cache = (key, roi)
        return self._roi_cache[1]

    # ---- sự kiện ----
    def _event_body(self, cfg: WorkerConfig, event: EngineEvent) -> dict[str, Any]:
        return {
            "event_uid": str(uuid.uuid4()),
            "camera_id": cfg.camera_id,
            "code": event.code.value,
            "priority": event.priority.value,
            "occurred_at": self._to_utc(event.occurred_at_ms).isoformat(),
            "detected_at": self._to_utc(event.detected_at_ms).isoformat(),
            "confidence": event.confidence,
            "observation_quality": event.observation_quality.value,
            "explanation": event.explanation,
            "config_hash": event.config_hash,
        }

    def _enqueue(self, body: dict[str, Any]) -> None:
        if len(self._events) >= self.options.event_queue_max:
            dropped = self._events.popleft()
            logger.warning("Hàng đợi sự kiện đầy: bỏ %s", dropped.body["code"])
        logger.info("Sự kiện %s (%s)", body["code"], body["priority"])
        self._events.append(_PendingEvent(body=body, next_try=0.0))

    def _flush_events(self, now: float) -> None:
        while self._events:
            if not self._api_open(self._clock()):
                return  # circuit mở: không gửi, chờ heartbeat thử lại API
            pending = self._events[0]
            if pending.next_try > now:
                return
            try:
                result = self.api.post_event(pending.body)
            except WorkerUnauthorizedError as exc:
                raise WorkerStopError(str(exc)) from exc
            if result is EventResult.RETRY:
                pending.attempts += 1
                delay = min(
                    self.options.retry_initial_s * 2 ** (pending.attempts - 1),
                    self.options.retry_max_s,
                )
                pending.next_try = now + delay
                self._mark_api_error(now, ApiUnavailableError("gửi sự kiện thất bại"))
                return
            self._events.popleft()

    def _wait_until(self, deadline: float) -> None:
        delay = deadline - self._clock()
        self._sleep(min(max(delay, 0.0), self.options.max_wait_s) or self.options.idle_s)
