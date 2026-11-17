"""F10 AC4: catalog sự kiện trong code khớp bảng §5 của event-engine.md."""

import re
from pathlib import Path

from postcare.schemas.enums import Priority
from postcare.schemas.events import ALERT_PRIORITIES, EVENT_CATALOG, EventCode, default_priority

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "docs" / "02-architecture" / "event-engine.md"
PRIORITY_RE = re.compile(r"\b(LOG|INFO|MEDIUM|HIGH)\b")


def _doc_table() -> dict[str, tuple[Priority, bool]]:
    """Đọc bảng catalog: Code → (mức ưu tiên đầu tiên của cột Priority, có tạo cảnh báo)."""
    section = DOC.read_text(encoding="utf-8").split("## 5.", 1)[1].split("\n## ", 1)[0]
    rows: dict[str, tuple[Priority, bool]] = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[0].startswith("`"):
            continue
        code = cells[0].strip("`")
        m = PRIORITY_RE.search(cells[2])
        assert m, f"không đọc được Priority của {code}: {cells[2]!r}"
        rows[code] = (Priority(m.group(1)), "Có" in cells[3])
    return rows


def test_doc_table_parsed() -> None:
    assert len(_doc_table()) == 14


def _code_side() -> dict[str, tuple[Priority, bool]]:
    return {
        code.value: (spec.default_priority, spec.creates_alert)
        for code, spec in EVENT_CATALOG.items()
    }


def _mismatches(
    code_side: dict[str, tuple[Priority, bool]], doc: dict[str, tuple[Priority, bool]]
) -> list[str]:
    return sorted(k for k in code_side.keys() | doc.keys() if code_side.get(k) != doc.get(k))


def test_catalog_matches_event_engine_doc() -> None:
    assert _mismatches(_code_side(), _doc_table()) == []


def test_catalog_covers_every_event_code() -> None:
    assert set(EVENT_CATALOG) == set(EventCode)
    assert len(EventCode) == 14


def test_creates_alert_only_medium_high() -> None:
    for code, spec in EVENT_CATALOG.items():
        assert spec.creates_alert == (spec.default_priority in ALERT_PRIORITIES), code
        assert spec.default_priority == default_priority(code)
    assert EVENT_CATALOG[EventCode.FACE_ATTENTION].default_priority == Priority.MEDIUM
    assert not EVENT_CATALOG[EventCode.SIT_UP].creates_alert
    assert EVENT_CATALOG[EventCode.BED_EXIT].creates_alert


def test_catalog_check_detects_drift() -> None:
    """Ca âm tính: thêm tạm một mã không có trong doc, hoặc đổi mức ưu tiên → phép so sánh đỏ."""
    doc = _doc_table()
    extra = {**_code_side(), "FAKE_CODE": (Priority.LOG, False)}
    assert _mismatches(extra, doc) == ["FAKE_CODE"]
    changed = {**_code_side(), "BED_EXIT": (Priority.MEDIUM, True)}
    assert _mismatches(changed, doc) == ["BED_EXIT"]
