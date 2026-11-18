"""F08 AC2: kiểm tra polygon Bed ROI, có mã lý do (`RoiPolygonError.reason`) cho API và web."""

from typing import Any

import pytest

from postcare.schemas.roi import MAX_ROI_POINTS, RoiPolygonError, validate_roi_polygon

SQUARE = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]


def _reason(points: Any) -> str:
    with pytest.raises(RoiPolygonError) as err:
        validate_roi_polygon(points)
    assert isinstance(err.value, ValueError)  # F12 vẫn bắt được bằng ValueError
    return err.value.reason


@pytest.mark.parametrize(
    "points",
    [
        SQUARE,
        [(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)],
        [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.5, 0.4), (0.1, 0.9)],  # lõm
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],  # đúng biên [0, 1]
    ],
)
def test_validate_roi_accepts_convex_and_concave(points: list[tuple[float, float]]) -> None:
    assert validate_roi_polygon(points).points == points


def test_validate_roi_accepts_max_points() -> None:
    import math

    pts = [
        (0.5 + 0.4 * math.cos(2 * math.pi * i / MAX_ROI_POINTS),
         0.5 + 0.4 * math.sin(2 * math.pi * i / MAX_ROI_POINTS))
        for i in range(MAX_ROI_POINTS)
    ]  # fmt: skip
    assert len(validate_roi_polygon(pts).points) == MAX_ROI_POINTS


def test_validate_roi_rejects_self_intersection() -> None:
    # Hình "nơ": hai cạnh không kề cắt nhau ở giữa.
    assert _reason([(0.1, 0.1), (0.9, 0.9), (0.9, 0.1), (0.1, 0.9)]) == "SELF_INTERSECTION"


def test_validate_roi_rejects_overlapping_edges() -> None:
    # Cạnh 3→0 đi ngược lại trên cạnh 0→1: chồng lên nhau.
    pts = [(0.1, 0.5), (0.9, 0.5), (0.9, 0.9), (0.5, 0.5)]
    assert _reason(pts) == "SELF_INTERSECTION"


def test_validate_roi_rejects_too_few_points() -> None:
    assert _reason([(0.1, 0.1), (0.9, 0.1)]) == "TOO_FEW_POINTS"
    assert _reason([]) == "TOO_FEW_POINTS"


def test_validate_roi_rejects_too_many_points() -> None:
    pts = [(0.01 * i, 0.5 + (0.1 if i % 2 else 0.0)) for i in range(MAX_ROI_POINTS + 1)]
    assert _reason(pts) == "TOO_MANY_POINTS"


@pytest.mark.parametrize(
    "points",
    [
        [(0.1, 0.1), (1.5, 0.1), (0.5, 0.9)],
        [(-0.01, 0.1), (0.9, 0.1), (0.5, 0.9)],
        [(0.1, 0.1), (0.9, 0.1), (0.5, 1.0001)],
    ],
)
def test_validate_roi_rejects_out_of_range(points: list[tuple[float, float]]) -> None:
    assert _reason(points) == "OUT_OF_RANGE"


@pytest.mark.parametrize(
    "points",
    [
        [(0.1, 0.1), (0.9,), (0.5, 0.9)],
        [(0.1, 0.1), ("0.9", 0.1), (0.5, 0.9)],
        [(0.1, 0.1), (True, 0.1), (0.5, 0.9)],
        [(0.1, 0.1), (float("nan"), 0.1), (0.5, 0.9)],
        [(0.1, 0.1), None, (0.5, 0.9)],
    ],
)
def test_validate_roi_rejects_non_numeric_points(points: Any) -> None:
    assert _reason(points) == "INVALID_POINT"


def test_validate_roi_rejects_collinear() -> None:
    assert _reason([(0.1, 0.1), (0.5, 0.5), (0.9, 0.9)]) == "ZERO_AREA"


def test_validate_roi_rejects_duplicate_points() -> None:
    assert _reason([(0.1, 0.1), (0.1, 0.1), (0.9, 0.1), (0.5, 0.9)]) == "DUPLICATE_POINT"
