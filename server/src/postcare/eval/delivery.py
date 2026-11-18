"""Đo delivery latency qua WebSocket (F29 R3, R4; HS §8.2; PDF §13.3; QA#37; A07).

Delivery latency = thời điểm client nhận `event.created` − `events.created_at`. Đây **không** phải
độ trễ phát hiện (hành động → màn hình, đã gồm `min_duration`); báo cáo ghi riêng hai số (QA#37).

Client đo chạy trên cùng máy với API để không lệch đồng hồ *(giả định R4)*; số đo chưa gồm độ
trễ Wi-Fi tới thiết bị khác. Mỗi mẫu ghi một dòng JSON vào `runs/<id>/delivery.jsonl` (gitignore).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from postcare.eval.metrics import percentile

EVENT_CREATED = "event.created"
WS_PATH = "/api/v1/ws"


@dataclass(frozen=True)
class DeliverySample:
    event_id: int
    code: str
    created_at: datetime
    received_at: datetime

    @property
    def latency_ms(self) -> float:
        return (self.received_at - self.created_at).total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "code": self.code,
            "created_at": self.created_at.isoformat(),
            "received_at": self.received_at.isoformat(),
            "latency_ms": round(self.latency_ms, 3),
        }


def _aware(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def sample_from_message(msg: Mapping[str, Any], received_at: datetime) -> DeliverySample | None:
    """Mẫu từ một message WS; message khác `event.created` hoặc thiếu trường → `None`."""
    if msg.get("type") != EVENT_CREATED:
        return None
    payload = msg.get("payload")
    if not isinstance(payload, Mapping):
        return None
    event_id, created = payload.get("id"), payload.get("created_at")
    if not isinstance(event_id, int) or not isinstance(created, str):
        return None
    return DeliverySample(event_id, str(payload.get("code", "")), _aware(created), received_at)


@dataclass
class DeliveryRecorder:
    """Ghi mẫu từ luồng message; bỏ trùng `event_id` (kết nối lại có thể nhận lại)."""

    samples: list[DeliverySample] = field(default_factory=list)
    _seen: set[int] = field(default_factory=set)

    def feed(self, msg: Mapping[str, Any], received_at: datetime) -> DeliverySample | None:
        sample = sample_from_message(msg, received_at)
        if sample is None or sample.event_id in self._seen:
            return None
        self._seen.add(sample.event_id)
        self.samples.append(sample)
        return sample


@dataclass(frozen=True)
class DeliveryStats:
    samples: int
    median_ms: float | None
    p90_ms: float | None
    max_ms: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "samples": self.samples,
            "median_ms": self.median_ms,
            "p90_ms": self.p90_ms,
            "max_ms": self.max_ms,
        }


def delivery_stats(samples: Sequence[DeliverySample]) -> DeliveryStats:
    lat = [s.latency_ms for s in samples]
    return DeliveryStats(
        samples=len(lat),
        median_ms=percentile(lat, 0.5),
        p90_ms=percentile(lat, 0.9),
        max_ms=max(lat) if lat else None,
    )


def write_sample(path: Path, sample: DeliverySample) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(sample.to_dict(), ensure_ascii=False) + "\n")


def read_samples(path: Path) -> list[DeliverySample]:
    out: list[DeliverySample] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            out.append(
                DeliverySample(
                    int(d["event_id"]),
                    str(d.get("code", "")),
                    _aware(d["created_at"]),
                    _aware(d["received_at"]),
                )
            )
    return out


def ws_url(api_base: str, token: str) -> str:
    """`http(s)://host` → `ws(s)://host/api/v1/ws?token=…`."""
    parts = urlsplit(api_base.rstrip("/"))
    scheme = "wss" if parts.scheme == "https" else "ws"
    return urlunsplit((scheme, parts.netloc, WS_PATH, f"token={quote(token)}", ""))


def login_token(api_base: str, username: str, password: str) -> str:
    """Đăng nhập bằng tài khoản nhân viên (dev/test) để lấy token cho WS."""
    import httpx

    r = httpx.post(
        f"{api_base.rstrip('/')}/api/v1/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    r.raise_for_status()
    return str(r.json()["access_token"])


async def record_delivery(
    url: str,
    duration_s: float,
    *,
    on_sample: Callable[[DeliverySample], None] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> list[DeliverySample]:
    """Kết nối WS, ghi mọi `event.created` trong `duration_s` giây. Thời điểm nhận lấy ngay khi
    nhận frame, trước khi parse JSON."""
    import websockets

    rec = DeliveryRecorder()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + duration_s
    async with websockets.connect(url, ping_interval=20) as ws:
        while (remaining := deadline - loop.time()) > 0:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 25.0))
            except TimeoutError:
                await ws.send(json.dumps({"type": "ping"}))
                continue
            received = clock()
            msg = json.loads(raw)
            sample = rec.feed(msg, received) if isinstance(msg, dict) else None
            if sample is not None and on_sample is not None:
                on_sample(sample)
    return rec.samples


def summarize(paths: Iterable[Path]) -> DeliveryStats:
    samples: list[DeliverySample] = []
    for p in paths:
        samples += read_samples(p)
    return delivery_stats(samples)
