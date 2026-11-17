"""`validate_roi_polygon` (F12 R3; dùng chung với F08): polygon đơn, diện tích > 0."""

import pytest

from postcare.schemas.roi import RoiPolygon, validate_roi_polygon


@pytest.mark.parametrize(
    "points",
    [
        [(0.2, 0.3), (0.8, 0.3), (0.8, 0.8), (0.2, 0.8)],
        [(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)],
        [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.5, 0.4), (0.1, 0.9)],  # lõm
    ],
)
def test_valid_polygons(points: list[tuple[float, float]]) -> None:
    roi = validate_roi_polygon(points)
    assert isinstance(roi, RoiPolygon)
    assert roi.points == points


@pytest.mark.parametrize(
    ("points", "needle"),
    [
        ([(0.1, 0.1), (0.9, 0.1)], "3"),
        ([(0, 0), (1, 1), (1, 0), (0, 1)], "tự cắt"),
        ([(0.1, 0.1), (0.5, 0.5), (0.9, 0.9)], "diện tích"),
        ([(0.1, 0.1), (0.1, 0.1), (0.9, 0.1), (0.5, 0.9)], "trùng"),
        ([(0.1, 0.1), (1.5, 0.1), (0.5, 0.9)], "[0, 1]"),
    ],
)
def test_invalid_polygons(points: list[tuple[float, float]], needle: str) -> None:
    with pytest.raises(ValueError) as err:
        validate_roi_polygon(points)
    assert needle in str(err.value)
