"""F37 AC3, R8: hai ca chồng giờ theo khoảng nửa mở `[start, end)` trên vòng 24 giờ."""

from datetime import time

import pytest

from postcare.domain.shifts import shifts_overlap


def _t(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _shift(span: str) -> tuple[time, time]:
    start, end = span.split("-")
    return _t(start), _t(end)


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        # Ca thường với ca thường.
        ("06:00-14:00", "14:00-22:00", False),  # kề nhau
        ("06:00-14:00", "13:00-15:00", True),
        ("06:00-14:00", "08:00-10:00", True),  # chứa nhau
        ("06:00-14:00", "06:00-14:00", True),  # trùng hệt
        ("06:00-08:00", "09:00-10:00", False),  # có khoảng trống
        # Ca qua nửa đêm với ca thường.
        ("14:00-22:00", "22:00-06:00", False),  # kề nhau (AC3)
        ("22:00-06:00", "06:00-14:00", False),  # kề nhau phía sau
        ("22:00-06:00", "21:00-23:00", True),
        ("22:00-06:00", "05:00-07:00", True),
        ("22:00-06:00", "00:00-01:00", True),  # nằm trọn sau nửa đêm
        ("22:00-06:00", "12:00-13:00", False),
        # Hai ca qua nửa đêm luôn cùng chứa 00:00.
        ("22:00-06:00", "23:00-01:00", True),
        ("22:00-02:00", "23:30-00:30", True),
    ],
)
def test_shifts_overlap_table(a: str, b: str, expected: bool) -> None:
    assert shifts_overlap(_shift(a), _shift(b)) is expected
    assert shifts_overlap(_shift(b), _shift(a)) is expected  # đối xứng
