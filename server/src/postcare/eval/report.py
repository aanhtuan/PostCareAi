"""Báo cáo đánh giá Markdown + JSON (F16 R6; evaluation.md mục 7, mục 8; HS §8.2; QA#33).

Báo cáo dùng nội bộ nhóm (không phải UI), nên giữ mã sự kiện (`BED_EXIT`…) để đối chiếu.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from postcare.eval.manifest import ManifestRow, TruthRow
from postcare.eval.matching import MatchResult, Prediction
from postcare.eval.metrics import CodeStats, code_stats, false_alerts_per_hour
from postcare.eval.perf import PerfSummary, aggregate_perf
from postcare.schemas.events import ALERT_PRIORITIES

TEAM_SOURCE = "team"


@dataclass(frozen=True)
class VideoResult:
    row: ManifestRow
    truths: list[TruthRow]
    match: MatchResult
    observed_s: float
    """Số giây trạng thái khác NO_OBSERVATION (từ `frames.jsonl`)."""
    total_s: float
    run: dict[str, Any] = field(default_factory=dict)

    @property
    def source(self) -> str:
        return self.row.source or TEAM_SOURCE


@dataclass
class EvalReport:
    split: str
    created: str
    videos: list[VideoResult]
    failures: list[tuple[str, str]]
    tol_before_s: float
    tol_after_s: float
    config_hashes: list[str]
    commit: str | None
    hardware: str
    mode: str
    manifest: str
    notes: list[str] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        return sum(v.row.duration_s for v in self.videos)


@dataclass(frozen=True)
class GroupStats:
    videos: int
    duration_s: float
    tp: int
    fp: int
    fn: int
    alert_fp: int
    observed_s: float
    total_s: float

    @property
    def coverage(self) -> float | None:
        return self.observed_s / self.total_s if self.total_s > 0 else None

    @property
    def false_alerts_per_hour(self) -> float | None:
        h = self.duration_s / 3600
        return self.alert_fp / h if h > 0 else None


def _group(videos: Sequence[VideoResult]) -> GroupStats:
    return GroupStats(
        videos=len(videos),
        duration_s=sum(v.row.duration_s for v in videos),
        tp=sum(len(v.match.tp) for v in videos),
        fp=sum(len(v.match.fp) for v in videos),
        fn=sum(len(v.match.fn) for v in videos),
        alert_fp=sum(1 for v in videos for p in v.match.fp if p.priority in ALERT_PRIORITIES),
        observed_s=sum(v.observed_s for v in videos),
        total_s=sum(v.total_s for v in videos),
    )


def _by(
    videos: Iterable[VideoResult], key: Callable[[VideoResult], str]
) -> dict[str, list[VideoResult]]:
    out: dict[str, list[VideoResult]] = defaultdict(list)
    for v in videos:
        out[key(v)].append(v)
    return dict(sorted(out.items()))


def _label_sources(videos: Iterable[VideoResult]) -> str:
    labels = sorted({t.label_source for v in videos for t in v.truths if t.label_source})
    return ", ".join(labels) if labels else "—"


def _fmt(x: float | None, digits: int = 2) -> str:
    return "—" if x is None else f"{x:.{digits}f}"


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f} %"


def _summary(report: EvalReport) -> tuple[GroupStats, PerfSummary, float | None]:
    g = _group(report.videos)
    perf = aggregate_perf(v.run for v in report.videos)
    fp = [p for v in report.videos for p in v.match.fp]
    return g, perf, false_alerts_per_hour(fp, report.duration_s / 3600)


def _code_table(stats: Sequence[CodeStats]) -> list[str]:
    lines = [
        "| Mã | TP | FP | FN | Precision | Recall | F1 | Latency trung vị (s) | Latency p90 (s) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in stats:
        lines.append(
            f"| {s.code.value} | {s.tp} | {s.fp} | {s.fn} | {_fmt(s.precision)} | "
            f"{_fmt(s.recall)} | {_fmt(s.f1)} | {_fmt(s.latency_median_s)} | "
            f"{_fmt(s.latency_p90_s)} |"
        )
    if not stats:
        lines.append("| — | 0 | 0 | 0 | — | — | — | — | — |")
    return lines


def _group_table(title: str, groups: dict[str, list[VideoResult]]) -> list[str]:
    lines = [
        f"| {title} | Video | Thời lượng (s) | TP | FP | FN | False alerts/giờ | Coverage |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, vids in groups.items():
        g = _group(vids)
        lines.append(
            f"| {name or '—'} | {g.videos} | {g.duration_s:.1f} | {g.tp} | {g.fp} | {g.fn} | "
            f"{_fmt(g.false_alerts_per_hour, 1)} | {_pct(g.coverage)} |"
        )
    return lines


def _source_code_table(groups: dict[str, list[VideoResult]]) -> list[str]:
    lines = [
        "| Nguồn | Nguồn nhãn | Mã | TP | FP | FN | Precision | Recall | F1 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, vids in groups.items():
        labels = _label_sources(vids)
        for s in code_stats(v.match for v in vids):
            lines.append(
                f"| {name} | {labels} | {s.code.value} | {s.tp} | {s.fp} | {s.fn} | "
                f"{_fmt(s.precision)} | {_fmt(s.recall)} | {_fmt(s.f1)} |"
            )
    return lines


def _fp_rows(report: EvalReport) -> list[tuple[Prediction, VideoResult]]:
    return [(p, v) for v in report.videos for p in v.match.fp]


def render_markdown(report: EvalReport) -> str:
    g, perf, fa_h = _summary(report)
    stats = code_stats(v.match for v in report.videos)
    ignored = sum(len(v.match.ignored) for v in report.videos)
    sources = _by(report.videos, lambda v: v.source)
    participants = {v.row.participant_id for v in report.videos if v.row.participant_id}
    hashes = ", ".join(f"`{h}`" for h in report.config_hashes) or "—"
    out: list[str] = [
        f"# Báo cáo đánh giá — split {report.split} — {report.created}",
        "",
        "Sinh bởi `postcare eval` (F16). Kết quả trên tập phát triển, dùng để hiệu chỉnh ngưỡng; "
        "không phải kết quả đánh giá chính thức (F29).",
        "",
        "## Thông tin chung",
        "",
        f"- Ngày: {report.created}",
        f"- Split: {report.split}",
        f"- config_hash: {hashes}",
        f"- Commit: `{report.commit or '—'}`",
        f"- Phần cứng: {report.hardware}",
        f"- Chế độ chạy: {report.mode}",
        f"- Manifest: `{report.manifest}`",
        f"- Số video: {len(report.videos)}"
        + (f" (thêm {len(report.failures)} video lỗi, không tính)" if report.failures else ""),
        f"- Tổng thời lượng: {report.duration_s:.1f} s ({report.duration_s / 60:.1f} phút)",
        f"- Tolerance ghép: [start − {report.tol_before_s:g} s, end + {report.tol_after_s:g} s] "
        "theo `occurred_at` (A06)",
        "- Nguồn dữ liệu: "
        + "; ".join(
            f"{name} ({len(vids)} video, nguồn nhãn: {_label_sources(vids)})"
            for name, vids in sources.items()
        ),
        *[f"- {n}" for n in report.notes],
        "",
        "## Bảng theo code",
        "",
        *_code_table(stats),
        "",
        f"Dự đoán bị bỏ qua vì mã không thuộc `eval_codes` của video (không tính FP): {ignored}.",
        "",
        "## Tổng hợp",
        "",
        f"- TP / FP / FN: {g.tp} / {g.fp} / {g.fn}",
        f"- False alerts/giờ (FP mức MEDIUM/HIGH): {_fmt(fa_h, 1)} ({g.alert_fp} FP)",
        f"- Coverage (thời gian không ở NO_OBSERVATION): {_pct(g.coverage)}",
        f"- FPS xử lý trung bình: {_fmt(perf.fps_processing, 1)}",
        f"- Khung bỏ: {perf.dropped_frames}",
        f"- CPU tiến trình (trung bình): {_fmt(perf.cpu_percent, 1)} %",
        f"- RAM đỉnh: {_fmt(perf.ram_peak_mb, 1)} MB",
        "",
        "## Theo nguồn dữ liệu và code",
        "",
        *_source_code_table(sources),
        "",
        "## Phân rã theo nguồn dữ liệu",
        "",
        *_group_table("Nguồn", sources),
        "",
        "## Phân rã theo camera_condition",
        "",
        *_group_table("camera_condition", _by(report.videos, lambda v: v.row.camera_condition)),
        "",
        "## Phân rã theo kịch bản",
        "",
        *_group_table("Kịch bản", _by(report.videos, lambda v: v.row.scenario)),
        "",
        "## Danh sách FP",
        "",
        "| Video | Mã | Mức | occurred (s) | detected (s) |",
        "|---|---|---|---|---|",
    ]
    for p, v in _fp_rows(report):
        out.append(
            f"| {v.row.video_id} | {p.code.value} | {p.priority.value} | "
            f"{p.occurred_s:.2f} | {p.detected_s:.2f} |"
        )
    out += [
        "",
        "## Danh sách FN",
        "",
        "| Video | Mã | start_s | end_s |",
        "|---|---|---|---|",
    ]
    for v in report.videos:
        for t in v.match.fn:
            out.append(
                f"| {v.row.video_id} | {t.event_code.value} | {t.start_s:.2f} | {t.end_s:.2f} |"
            )
    if report.failures:
        out += ["", "## Video lỗi (không tính)", "", "| Video | Lỗi |", "|---|---|"]
        out += [f"| {vid} | {msg} |" for vid, msg in report.failures]
    external = [s for s in sources if s != TEAM_SOURCE]
    out += [
        "",
        "## Giới hạn",
        "",
        "- Tình huống mô phỏng hoặc dữ liệu ngoài; không phải bệnh nhân thật (HS §7.2).",
        f"- Số người tham gia khác nhau (`participant_id`): {len(participants)}.",
        "- Kết quả trên tập dev chỉ để hiệu chỉnh ngưỡng; không dùng làm con số cuối (HS §8.2).",
    ]
    if external:
        out += [
            f"- Có dữ liệu ngoài ({', '.join(external)}): kết quả tách theo nguồn và nguồn nhãn "
            "(evaluation.md §8). Truth chỉ đầy đủ với các mã trong `eval_codes`.",
            "- Metric BED_EDGE / STAND_UP / BED_EXIT trên dữ liệu ngoài chỉ để tham khảo: không có "
            "video công khai quay rời giường bằng camera cố định theo camera-setup.md "
            "(datasets.md §5).",
        ]
    return "\n".join(out) + "\n"


def _code_dict(s: CodeStats) -> dict[str, Any]:
    return {
        "code": s.code.value,
        "tp": s.tp,
        "fp": s.fp,
        "fn": s.fn,
        "precision": s.precision,
        "recall": s.recall,
        "f1": s.f1,
        "latency_median_s": s.latency_median_s,
        "latency_p90_s": s.latency_p90_s,
    }


def _pred_dict(p: Prediction) -> dict[str, Any]:
    return {
        "code": p.code.value,
        "priority": p.priority.value,
        "occurred_s": p.occurred_s,
        "detected_s": p.detected_s,
    }


def _truth_dict(t: TruthRow) -> dict[str, Any]:
    return {"code": t.event_code.value, "start_s": t.start_s, "end_s": t.end_s}


RUN_KEYS = (
    "mode",
    "camera_config",
    "config_hash",
    "frames",
    "dropped_frames",
    "fps_processing",
    "cpu_percent",
    "ram_peak_mb",
    "elapsed_s",
)


def report_json(report: EvalReport) -> dict[str, Any]:
    g, perf, fa_h = _summary(report)
    return {
        "split": report.split,
        "created": report.created,
        "config_hashes": report.config_hashes,
        "commit": report.commit,
        "hardware": report.hardware,
        "mode": report.mode,
        "manifest": report.manifest,
        "tolerance_s": {"before": report.tol_before_s, "after": report.tol_after_s},
        "summary": {
            "videos": len(report.videos),
            "duration_s": report.duration_s,
            "tp": g.tp,
            "fp": g.fp,
            "fn": g.fn,
            "false_alerts_per_hour": fa_h,
            "coverage": g.coverage,
            "fps_processing": perf.fps_processing,
            "dropped_frames": perf.dropped_frames,
            "cpu_percent": perf.cpu_percent,
            "ram_peak_mb": perf.ram_peak_mb,
        },
        "per_code": [_code_dict(s) for s in code_stats(v.match for v in report.videos)],
        "per_source": {
            name: {
                "label_source": _label_sources(vids),
                "per_code": [_code_dict(s) for s in code_stats(v.match for v in vids)],
            }
            for name, vids in _by(report.videos, lambda v: v.source).items()
        },
        "videos": [
            {
                "video_id": v.row.video_id,
                "source": v.source,
                "scenario": v.row.scenario,
                "camera_condition": v.row.camera_condition,
                "duration_s": v.row.duration_s,
                "coverage": v.observed_s / v.total_s if v.total_s > 0 else None,
                "tp": [
                    {**_truth_dict(m.truth), "prediction": _pred_dict(m.prediction)}
                    for m in v.match.tp
                ],
                "fp": [_pred_dict(p) for p in v.match.fp],
                "fn": [_truth_dict(t) for t in v.match.fn],
                "ignored": [_pred_dict(p) for p in v.match.ignored],
                "run": {k: v.run.get(k) for k in RUN_KEYS},
            }
            for v in report.videos
        ],
        "failures": [{"video_id": vid, "error": msg} for vid, msg in report.failures],
        "notes": report.notes,
    }
