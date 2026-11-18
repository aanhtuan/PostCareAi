"""F29 R8, R9, AC4: báo cáo đánh giá chính thức có đủ mục (dữ liệu giả, không media)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from postcare.eval.delivery import DeliverySample, delivery_stats

from postcare.eval.report import FinalExtras, final_report_json, render_final_markdown
from tests.eval.test_report import HASH, _report

T0 = datetime(2026, 11, 18, 3, 0, tzinfo=UTC)

WORKFLOW = {
    "from": "2026-11-18T02:00:00+00:00",
    "to": "2026-11-18T03:00:00+00:00",
    "alerts": 5,
    "ack_samples": 4,
    "ack_wait_median_s": 45.0,
    "ack_wait_p90_s": 81.0,
    "resolve_samples": 3,
    "resolve_median_s": 120.0,
    "resolve_p90_s": 264.0,
    "resolved": 3,
    "resolved_with_outcome": 2,
    "outcome_rate": 2 / 3,
    "with_outcome": 2,
    "false_alarm": 1,
    "false_alarm_rate": 0.5,
    "pending_at_end": 1,
    "acknowledged_at_end": 1,
}


def _extras(**kw: object) -> FinalExtras:
    samples = [
        DeliverySample(i, "BED_EXIT", T0, T0 + timedelta(milliseconds=ms))
        for i, ms in enumerate([12.0, 20.0, 35.0])
    ]
    base = FinalExtras(
        frozen_hash=HASH,
        frozen_file="reports/frozen-config.txt",
        delivery=delivery_stats(samples),
        delivery_source="runs/d1/delivery.jsonl",
        workflow=WORKFLOW,
        workflow_source="runs/d1/workflow.json",
    )
    return replace(base, **kw)  # type: ignore[arg-type]


def _final() -> str:
    report = replace(_report(), split="test")
    return render_final_markdown(report, _extras())


def test_final_report_has_required_sections() -> None:
    md = _final()
    for needle in (
        "## Chốt cấu hình",
        f"`{HASH}`",
        "## Bảng theo code",
        "| BED_EXIT | 1 | 0 | 0 |",
        "Precision",
        "Recall",
        "F1",
        "False alerts/giờ",
        "## Độ trễ",
        "Detection latency",
        "Delivery latency",
        "3 mẫu",
        "20",  # trung vị ms
        "Coverage",
        "FPS",
        "CPU",
        "RAM",
        "Khung bỏ",
        "## Workflow",
        "45.0",  # chờ tiếp nhận trung vị
        "264.0",
        "66.7 %",  # tỷ lệ có ghi kết quả
        "50.0 %",  # tỷ lệ cảnh báo sai
        "Phần cứng",
        "Tổng thời lượng",
        "camera_condition",
        "Commit",
        "## Giới hạn",
    ):
        assert needle in md, needle
    assert "đánh giá chính thức" in md
    # R9: không đặt trước chỉ tiêu accuracy
    assert "chỉ tiêu" not in md.lower() or "không đặt trước" in md.lower()


def test_final_report_missing_delivery_says_not_measured() -> None:
    md = render_final_markdown(
        replace(_report(), split="test"),
        _extras(delivery=None, delivery_source=None, workflow=None),
    )
    assert "Delivery latency: chưa đo" in md
    assert "Workflow: chưa đo" in md


def test_final_report_zero_delivery_samples() -> None:
    md = render_final_markdown(
        replace(_report(), split="test"), _extras(delivery=delivery_stats([]))
    )
    assert "0 mẫu" in md


def test_final_report_json_has_extras() -> None:
    data = final_report_json(replace(_report(), split="test"), _extras())
    assert data["frozen_config_hash"] == HASH
    assert data["delivery"]["samples"] == 3
    assert data["workflow"]["alerts"] == 5
