"""F16 AC4, R6: báo cáo Markdown/JSON theo mẫu evaluation.md mục 7 (dữ liệu giả)."""

import json

import pytest

from postcare.eval.manifest import ManifestRow, TruthRow
from postcare.eval.matching import match_events
from postcare.eval.report import EvalReport, VideoResult, render_markdown, report_json
from postcare.schemas.events import EventCode
from tests.eval.helpers import pred

HASH = "ab12cd34" * 8


def _row(video_id: str, condition: str, **kw: str) -> ManifestRow:
    return ManifestRow(
        video_id=video_id,
        path=f"data/videos/{video_id}.mp4",
        split="dev",
        participant_id="P01",
        session_id="day1",
        camera_condition=condition,
        duration_s=60.0,
        notes=kw.pop("notes", ""),
        **kw,
    )


def _report() -> EvalReport:
    v1 = _row("S06_P01_r1", "tripod-head-left;light-normal")
    t1 = [TruthRow(video_id=v1.video_id, event_code=EventCode.BED_EXIT, start_s=27.0, end_s=27.0)]
    m1 = match_events(
        [
            pred(EventCode.BED_EXIT, 27.5, detected_s=29.0, video_id=v1.video_id),
            pred(EventCode.BED_EDGE, 40.25, video_id=v1.video_id),
        ],
        t1,
    )
    v2 = _row(
        "urfd_fall01_cam0",
        "fixed-front-side;light-normal",
        source="URFD",
        notes="scenario=S15(nga xuong san);eval_codes=ABNORMAL_MOVEMENT",
    )
    t2 = [
        TruthRow(
            video_id=v2.video_id,
            event_code=EventCode.ABNORMAL_MOVEMENT,
            start_s=2.73,
            end_s=3.73,
            label_source="dataset",
        )
    ]
    m2 = match_events([], t2, eval_codes=v2.eval_codes)
    run = {
        "config_hash": HASH,
        "frames": 900,
        "elapsed_s": 50.0,
        "dropped_frames": 3,
        "cpu_percent": 120.0,
        "ram_peak_mb": 290.0,
    }
    return EvalReport(
        split="dev",
        created="2026-11-18",
        videos=[
            VideoResult(v1, t1, m1, observed_s=50.0, total_s=60.0, run=run),
            VideoResult(v2, t2, m2, observed_s=30.0, total_s=60.0, run=run),
        ],
        failures=[("S07_P01_r1", "Không mở được video")],
        tol_before_s=1.0,
        tol_after_s=3.0,
        config_hashes=[HASH],
        commit="deadbeef",
        hardware="test-cpu, 8 luồng",
        mode="video",
        manifest="data/eval/manifest.csv",
    )


def test_report_contains_required_sections() -> None:
    md = render_markdown(_report())
    for needle in (
        "dev",
        "2026-11-18",
        HASH,
        "deadbeef",
        "test-cpu",
        "Số video: 2",
        "2.0 phút",  # tổng thời lượng 120 s
        "[start − 1 s, end + 3 s]",
        "| BED_EXIT | 1 | 0 | 0 |",
        "| ABNORMAL_MOVEMENT | 0 | 0 | 1 |",
        "| BED_EDGE | 0 | 1 | 0 |",
        "False alerts/giờ",
        "Coverage",
        "FPS",
        "Khung bỏ",
        "CPU",
        "RAM",
        "tripod-head-left;light-normal",
        "fixed-front-side;light-normal",
        "S06",
        "S15",
        "## Danh sách FP",
        "40.25",
        "## Danh sách FN",
        "2.73",
        "S07_P01_r1",
        "## Giới hạn",
    ):
        assert needle in md, needle
    assert "\r\n" not in md


def test_report_marks_external_sources() -> None:
    md = render_markdown(_report())
    assert "URFD" in md
    assert "dataset" in md  # nguồn nhãn (evaluation.md §8; QA#33)


def test_report_json_round_trip() -> None:
    data = report_json(_report())
    text = json.dumps(data, ensure_ascii=False)
    loaded = json.loads(text)
    assert loaded["split"] == "dev"
    codes = {c["code"]: c for c in loaded["per_code"]}
    assert codes["BED_EXIT"]["tp"] == 1
    assert codes["BED_EXIT"]["latency_median_s"] == 2.0
    assert loaded["summary"]["false_alerts_per_hour"] == pytest.approx(30.0)  # 1 FP MEDIUM / 2 phút
    assert loaded["summary"]["coverage"] == pytest.approx(80.0 / 120.0)
