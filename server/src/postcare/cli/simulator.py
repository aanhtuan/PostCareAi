"""Giả lập worker (thay AI/camera trong prototype, ADR-0010).

Gửi trạng thái giường và sự kiện qua API nội bộ giống hệt worker thật sẽ làm:
`POST /internal/v1/cameras/{id}/state`, `POST /internal/v1/events` (idempotent theo `event_uid`),
heartbeat mỗi 2 giây (A02).
"""

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from postcare.schemas.enums import (
    ActivityLevel,
    BodyState,
    FaceStatus,
    ObservationQuality,
    Priority,
    RestStatus,
)
from postcare.schemas.events import EventCode, default_priority

HEARTBEAT_INTERVAL_S = 2.0  # A02


@dataclass(frozen=True)
class Step:
    wait_s: float
    body_state: BodyState
    note: str
    event: EventCode | None = None
    priority: Priority | None = None
    quality: ObservationQuality = ObservationQuality.GOOD
    activity: ActivityLevel = ActivityLevel.NORMAL
    rest: RestStatus = RestStatus.UNKNOWN
    face_status: FaceStatus = FaceStatus.NOT_VISIBLE
    face_signals: dict[str, bool] = field(default_factory=dict)


def _bed_exit(away_s: float) -> list[Step]:
    """Kịch bản demo chính HS §8.3."""
    b = BodyState
    return [
        Step(0, b.LYING, "Nằm trên giường", activity=ActivityLevel.LOW),
        Step(3, b.RAISING, "Đang nâng thân"),
        Step(1.5, b.SITTING, "Ngồi dậy", EventCode.SIT_UP),
        Step(3, b.AT_EDGE, "Di chuyển tới mép giường", EventCode.BED_EDGE),
        Step(3, b.STANDING, "Đứng lên", EventCode.STAND_UP),
        Step(2, b.OUT_OF_BED, "Bước khỏi vùng giường", EventCode.BED_EXIT),
        Step(away_s, b.SITTING, "Quay lại giường", EventCode.RETURN_TO_BED),
        Step(2, b.LYING, "Nằm lại", activity=ActivityLevel.LOW),
    ]


def _observation_lost(away_s: float) -> list[Step]:
    b = BodyState
    no_person = ObservationQuality.NO_PERSON
    unknown = ActivityLevel.UNKNOWN
    return [
        Step(0, b.LYING, "Nằm trên giường", activity=ActivityLevel.LOW),
        Step(
            3,
            b.NO_OBSERVATION,
            "Camera bị che / không thấy người",
            quality=no_person,
            activity=unknown,
        ),
        Step(
            10,
            b.NO_OBSERVATION,
            "Mất quan sát kéo dài",
            EventCode.OBSERVATION_LOST,
            quality=no_person,
            activity=unknown,
        ),
        Step(
            max(away_s / 2, 3),
            b.LYING,
            "Quan sát lại được",
            EventCode.OBSERVATION_RESTORED,
            activity=ActivityLevel.LOW,
        ),
    ]


def _abnormal_movement(away_s: float) -> list[Step]:
    b = BodyState
    return [
        Step(0, b.LYING, "Nằm trên giường", activity=ActivityLevel.LOW),
        Step(2, b.SITTING, "Ngồi dậy", EventCode.SIT_UP),
        Step(2, b.AT_EDGE, "Ở mép giường", EventCode.BED_EDGE),
        Step(2, b.STANDING, "Đứng lên", EventCode.STAND_UP),
        Step(1.5, b.OUT_OF_BED, "Rời vùng giường", EventCode.BED_EXIT),
        Step(
            1.5,
            b.OUT_OF_BED,
            "Hông hạ nhanh, vị trí thấp, giữ nguyên",
            EventCode.ABNORMAL_MOVEMENT,
            activity=ActivityLevel.HIGH,
        ),
        Step(away_s, b.SITTING, "Được hỗ trợ quay lại giường", EventCode.RETURN_TO_BED),
        Step(2, b.LYING, "Nằm lại", activity=ActivityLevel.LOW),
    ]


def _face_attention(_away_s: float) -> list[Step]:
    b = BodyState
    ok = FaceStatus.OK
    signals = {"brow_down": True, "eye_squint": True}
    return [
        Step(0, b.LYING, "Nằm, mặt rõ", activity=ActivityLevel.LOW, face_status=ok),
        Step(
            3,
            b.LYING,
            "Hạ lông mày + nheo mắt",
            activity=ActivityLevel.LOW,
            face_status=ok,
            face_signals=signals,
        ),
        Step(
            5,
            b.LYING,
            "Tín hiệu mặt duy trì đủ lâu",
            EventCode.FACE_ATTENTION,
            activity=ActivityLevel.LOW,
            face_status=ok,
            face_signals=signals,
        ),
        Step(5, b.LYING, "Tín hiệu mặt hết", activity=ActivityLevel.LOW, face_status=ok),
    ]


def _posture_change(_away_s: float) -> list[Step]:
    b = BodyState
    return [
        Step(0, b.LYING, "Nằm ngửa", activity=ActivityLevel.LOW),
        Step(3, b.LYING, "Trở mình sang bên", EventCode.POSTURE_CHANGE),
        Step(3, b.LYING, "Nằm yên", activity=ActivityLevel.LOW),
    ]


SCENARIOS: dict[str, Callable[[float], list[Step]]] = {
    "bed-exit": _bed_exit,
    "observation-lost": _observation_lost,
    "abnormal-movement": _abnormal_movement,
    "face-attention": _face_attention,
    "posture-change": _posture_change,
}


class Simulator:
    def __init__(
        self,
        *,
        base_url: str,
        worker_token: str,
        camera_id: int,
        log: Callable[[str], None] = print,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        headers = {"X-Worker-Token": worker_token}
        self.client = httpx.Client(
            base_url=base_url, headers=headers, timeout=10, transport=transport
        )
        self._hb_client = httpx.Client(
            base_url=base_url, headers=headers, timeout=5, transport=transport
        )
        self.camera_id = camera_id
        self.log = log
        self.sleep = sleep
        self._stop = threading.Event()
        self._hb_thread: threading.Thread | None = None

    # ---- kết nối ----
    def config(self) -> dict[str, Any]:
        r = self.client.get(f"/internal/v1/cameras/{self.camera_id}/config")
        r.raise_for_status()
        return r.json()

    def heartbeat_once(self) -> None:
        self._hb_client.post(
            f"/internal/v1/cameras/{self.camera_id}/heartbeat",
            json={"fps": 15.0, "brightness": 0.6, "dropped_frames": 0, "source_status": "SIM"},
        )

    def start_heartbeat(self) -> None:
        def _loop() -> None:
            while not self._stop.is_set():
                try:
                    self.heartbeat_once()
                except httpx.HTTPError as exc:
                    self.log(f"  ! heartbeat lỗi: {exc}")
                self._stop.wait(HEARTBEAT_INTERVAL_S)

        self._hb_thread = threading.Thread(target=_loop, daemon=True)
        self._hb_thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._hb_thread:
            self._hb_thread.join(timeout=3)
        self.client.close()
        self._hb_client.close()

    # ---- gửi dữ liệu ----
    def send_state(self, step: Step) -> None:
        body = {
            "body_state": step.body_state.value,
            "observation_quality": step.quality.value,
            "activity_level": step.activity.value,
            "rest_status": step.rest.value,
            "face_status": step.face_status.value,
            "face_signals": step.face_signals,
            "ts": datetime.now(UTC).isoformat(),
        }
        self.client.post(
            f"/internal/v1/cameras/{self.camera_id}/state", json=body
        ).raise_for_status()

    def send_event(self, step: Step, scenario: str) -> dict[str, Any] | None:
        assert step.event is not None
        now = datetime.now(UTC)
        body = {
            "event_uid": str(uuid.uuid4()),
            "camera_id": self.camera_id,
            "code": step.event.value,
            "priority": (step.priority or default_priority(step.event)).value,
            "occurred_at": (now - timedelta(milliseconds=500)).isoformat(),
            "detected_at": now.isoformat(),
            "confidence": 0.9,
            "observation_quality": step.quality.value,
            "explanation": {
                "rule_id": f"simulator.{step.event.value.lower()}",
                "source": "simulator",
                "scenario": scenario,
            },
            "config_hash": "simulator",
        }
        # Gửi lại khi lỗi mạng / 5xx: dùng lại cùng event_uid (event-engine.md mục 7).
        for attempt in range(3):
            try:
                r = self.client.post("/internal/v1/events", json=body)
            except httpx.TransportError as exc:
                self.log(f"  ! lỗi mạng, gửi lại ({attempt + 1}/3): {exc}")
                self.sleep(1)
                continue
            if r.status_code >= 500:
                self.sleep(1)
                continue
            if r.status_code == 409:
                self.log(f"  ! API từ chối sự kiện: {r.json()['error']['message']}")
                return None
            r.raise_for_status()
            return r.json()
        return None

    def run(self, scenario: str, *, speed: float, away_s: float, repeat: int, gap_s: float) -> None:
        steps = SCENARIOS[scenario](away_s)
        for i in range(repeat):
            if repeat > 1:
                self.log(f"--- Lượt {i + 1}/{repeat} ---")
            for step in steps:
                if step.wait_s:
                    self.sleep(step.wait_s / speed)
                self.send_state(step)
                line = f"[{datetime.now().strftime('%H:%M:%S')}] {step.note} -> {step.body_state}"
                if step.event:
                    res = self.send_event(step, scenario)
                    line += f" | sự kiện {step.event}"
                    if res:
                        line += f" (id={res['id']})"
                self.log(line)
            if i < repeat - 1:
                self.sleep(gap_s / speed)
