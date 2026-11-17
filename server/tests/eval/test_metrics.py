"""F16 AC3, R5: P/R/F1, false alerts/giờ, latency, coverage, hiệu năng (số liệu tính tay)."""

import pytest
from postcare.eval.manifest import TruthRow
from postcare.eval.matching import MatchResult, match_events
from postcare.eval.metrics import (
    code_stats,
    coverage_seconds,
    false_alerts_per_hour,
    latency_stats,
    prf,
)
from postcare.eval.perf import aggregate_perf

from postcare.schemas.enums import BodyState, Priority
from postcare.schemas.events import EventCode
from tests.eval.helpers import pred

NO_OBS = BodyState.NO_OBSERVATION
LYING = BodyState.LYING


def test_false_alerts_per_hour_counts_only_medium_high() -> None:
    fps = [
        pred(EventCode.BED_EXIT, 1.0),  # HIGH
        pred(EventCode.ABNORMAL_MOVEMENT, 2.0),  # HIGH
        pred(EventCode.SIT_UP, 3.0),  # INFO: không tính
        pred(EventCode.POSTURE_CHANGE, 4.0),  # LOG: không tính
    ]
    assert false_alerts_per_hour(fps, total_hours=0.5) == pytest.approx(4.0)
    medium = [pred(EventCode.BED_EDGE, 1.0)]
    assert medium[0].priority == Priority.MEDIUM
    assert false_alerts_per_hour(medium, total_hours=2.0) == pytest.approx(0.5)
    assert false_alerts_per_hour(fps, total_hours=0.0) is None


def test_latency_median_p90() -> None:
    median, p90 = latency_stats([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    assert median == pytest.approx(5.5)
    assert p90 == pytest.approx(9.1)  # nội suy tuyến tính
    assert latency_stats([]) == (None, None)
    assert latency_stats([2.0]) == (2.0, 2.0)


def test_latency_is_detected_minus_truth_start() -> None:
    gt = [TruthRow(video_id="v1", event_code=EventCode.BED_EXIT, start_s=20.0, end_s=25.0)]
    r = match_events([pred(EventCode.BED_EXIT, 21.0, detected_s=23.5)], gt)
    [stats] = code_stats([r])
    assert stats.latency_median_s == pytest.approx(3.5)


def test_coverage_excludes_no_observation() -> None:
    # 10 khung cách 100 ms; 4 khung NO_OBSERVATION → 60 % thời gian có quan sát.
    frames = [(i * 100, NO_OBS if i in (0, 1, 2, 3) else LYING) for i in range(10)]
    observed, total = coverage_seconds(frames)
    assert total == pytest.approx(1.0)
    assert observed == pytest.approx(0.6)
    assert coverage_seconds([(0, NO_OBS)] * 0) == (0.0, 0.0)


def test_coverage_is_time_weighted() -> None:
    # Khung 0 kéo dài 0,1 s (LYING), khung 1 kéo dài 0,9 s (NO_OBSERVATION), khung cuối 0,5 s.
    frames = [(0, LYING), (100, NO_OBS), (1000, LYING)]
    observed, total = coverage_seconds(frames)
    assert total == pytest.approx(1.5)  # bước cuối = trung vị bước (0,5 s)
    assert observed == pytest.approx(0.6)


def test_prf_zero_denominator_is_none() -> None:
    assert prf(0, 0, 0) == (None, None, None)
    assert prf(0, 2, 0) == (0.0, None, None)
    p, r, f1 = prf(3, 1, 2)
    assert p == pytest.approx(0.75)
    assert r == pytest.approx(0.6)
    assert f1 == pytest.approx(2 * 0.75 * 0.6 / 1.35)


def test_code_stats_per_code() -> None:
    gt = [
        TruthRow(video_id="v1", event_code=EventCode.SIT_UP, start_s=1.0, end_s=2.0),
        TruthRow(video_id="v1", event_code=EventCode.BED_EXIT, start_s=10.0, end_s=10.0),
    ]
    results: list[MatchResult] = [
        match_events([pred(EventCode.SIT_UP, 1.5), pred(EventCode.SIT_UP, 30.0)], gt),
    ]
    by_code = {s.code: s for s in code_stats(results)}
    assert (by_code[EventCode.SIT_UP].tp, by_code[EventCode.SIT_UP].fp) == (1, 1)
    assert by_code[EventCode.SIT_UP].precision == pytest.approx(0.5)
    assert (by_code[EventCode.BED_EXIT].fn, by_code[EventCode.BED_EXIT].recall) == (1, 0.0)
    assert by_code[EventCode.BED_EXIT].precision is None


def test_perf_aggregate() -> None:
    runs = [
        {
            "frames": 100,
            "elapsed_s": 10.0,
            "dropped_frames": 5,
            "cpu_percent": 100.0,
            "ram_peak_mb": 300.0,
        },
        {
            "frames": 300,
            "elapsed_s": 10.0,
            "dropped_frames": 7,
            "cpu_percent": 50.0,
            "ram_peak_mb": 280.0,
        },
    ]
    perf = aggregate_perf(runs)
    assert perf.fps_processing == pytest.approx(20.0)  # 400 khung / 20 s
    assert perf.dropped_frames == 12
    assert perf.cpu_percent == pytest.approx(75.0)  # trung bình theo thời gian chạy
    assert perf.ram_peak_mb == pytest.approx(300.0)
    assert aggregate_perf([]).fps_processing is None
