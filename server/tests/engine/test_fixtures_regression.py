"""F12 R8: chạy engine trên mọi fixture `server/tests/fixtures/*.jsonl` có `.expected.json`.

Fixture chỉ chứa toạ độ (`FrameObservation`), cắt bằng
`postcare replay --from-observations … --save-observations … --save-expected` (testing.md §2).
Thiếu `.expected.json` → ca bị bỏ qua kèm lý do. Đổi ngưỡng làm lệch sự kiện → sinh lại expected,
xem lại so với ground truth rồi commit.
"""

from pathlib import Path

import pytest
from postcare.replay.fixtures import FixtureCase, discover_fixtures, run_fixture

from postcare.settings import REPO_ROOT

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
DEFAULT_ENGINE = REPO_ROOT / "config" / "engine.default.yaml"

CASES = [
    pytest.param(
        case,
        id=case.name,
        marks=[] if case.expected is not None else [pytest.mark.skip(reason=case.skip_reason)],
    )
    for case in discover_fixtures(FIXTURES_DIR)
]


@pytest.mark.parametrize("case", CASES)
def test_fixtures_regression(case: FixtureCase) -> None:
    actual, expected = run_fixture(case, DEFAULT_ENGINE)
    assert actual == expected
