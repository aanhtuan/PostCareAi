"""F29 R3, R4, AC2: delivery latency = lúc client WS nhận `event.created` − `events.created_at`."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from postcare.eval.delivery import (
    DeliveryRecorder,
    DeliverySample,
    delivery_stats,
    read_samples,
    sample_from_message,
    write_sample,
    ws_url,
)

T0 = datetime(2026, 11, 18, 3, 0, tzinfo=UTC)


def _msg(event_id: int, created_at: datetime, type_: str = "event.created") -> dict[str, object]:
    return {
        "type": type_,
        "payload": {"id": event_id, "code": "BED_EXIT", "created_at": created_at.isoformat()},
        "sent_at": created_at.isoformat(),
    }


def _sample(latency_ms: float, event_id: int = 1) -> DeliverySample:
    return DeliverySample(
        event_id=event_id,
        code="SIT_UP",
        created_at=T0,
        received_at=T0 + timedelta(milliseconds=latency_ms),
    )


def test_delivery_record_from_message() -> None:
    s = sample_from_message(_msg(7, T0), T0 + timedelta(milliseconds=42))
    assert s is not None
    assert s.event_id == 7 and s.code == "BED_EXIT"
    assert s.latency_ms == pytest.approx(42.0)


def test_only_event_created_is_recorded() -> None:
    assert sample_from_message(_msg(1, T0, "alert.created"), T0) is None
    assert sample_from_message({"type": "event.created", "payload": {}}, T0) is None


def test_naive_created_at_is_utc() -> None:
    """`EventOut.created_at` không bắt buộc có múi giờ: coi là UTC (data-model: lưu UTC)."""
    msg = _msg(1, T0)
    msg["payload"]["created_at"] = T0.replace(tzinfo=None).isoformat()  # type: ignore[index]
    s = sample_from_message(msg, T0 + timedelta(milliseconds=5))
    assert s is not None and s.latency_ms == pytest.approx(5.0)


def test_recorder_skips_duplicate_event_ids() -> None:
    rec = DeliveryRecorder()
    assert rec.feed(_msg(1, T0), T0 + timedelta(milliseconds=10)) is not None
    assert rec.feed(_msg(1, T0), T0 + timedelta(milliseconds=90)) is None
    assert rec.feed(_msg(2, T0, "alert.updated"), T0) is None
    assert [s.event_id for s in rec.samples] == [1]


def test_delivery_stats_median_p90() -> None:
    stats = delivery_stats(
        [_sample(ms, i) for i, ms in enumerate([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])]
    )
    assert stats.samples == 10
    assert stats.median_ms == pytest.approx(55.0)
    assert stats.p90_ms == pytest.approx(91.0)
    assert stats.max_ms == pytest.approx(100.0)


def test_delivery_stats_zero_samples() -> None:
    stats = delivery_stats([])
    assert stats.samples == 0
    assert stats.median_ms is None and stats.p90_ms is None and stats.max_ms is None


def test_samples_jsonl_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "runs" / "d1" / "delivery.jsonl"
    for s in (_sample(12.5, 1), _sample(30.0, 2)):
        write_sample(path, s)
    back = read_samples(path)
    assert [round(s.latency_ms, 1) for s in back] == [12.5, 30.0]


def test_ws_url_from_api_base() -> None:
    assert ws_url("http://127.0.0.1:8029", "abc") == "ws://127.0.0.1:8029/api/v1/ws?token=abc"
    assert ws_url("https://h.test/", "x y") == "wss://h.test/api/v1/ws?token=x%20y"
