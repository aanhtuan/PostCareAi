"""F14 R3, R4, R5: phân loại tư thế, vị trí thô và ánh xạ sang trạng thái ứng viên.

Dùng `BodyFeatures` tổng hợp (không qua làm mượt) để kiểm đúng từng ngưỡng của
`config/engine.default.yaml`. Giá trị lấy từ config, không viết cứng ngưỡng.
"""

import pytest

from postcare.engine.features import BodyFeatures
from postcare.engine.geometry import Px
from postcare.engine.posture import (
    Location,
    Posture,
    candidate_state,
    classify_location,
    classify_posture,
)
from postcare.schemas.state import BodyState as S
from tests.engine.builders import default_config

CONFIG = default_config()
P = CONFIG.posture
LOC = CONFIG.location
HIP: Px = (640.0, 400.0)
TORSO = 200.0


def feat(
    angle: float = 0.0,
    *,
    dist: float = 0.9,
    ankles_out: int = 0,
    torso: float = TORSO,
    shoulder_above_hip: bool = True,
    knee: Px | None = None,
    ankle: Px | None = None,
    leg_angle: float | None = None,
) -> BodyFeatures:
    """`knee`, `ankle`: vector lệch so với tâm hông (pixel, y hướng xuống)."""
    hx, hy = HIP
    shoulder = (hx, hy - torso / 2) if shoulder_above_hip else (hx, hy + torso / 2)
    k = None if knee is None else (hx + knee[0], hy + knee[1])
    a = None if ankle is None else (hx + ankle[0], hy + ankle[1])
    return BodyFeatures(
        ts_ms=0,
        image_size=(1280, 720),
        hip_center=HIP,
        shoulder_center=shoulder,
        torso_length=torso,
        trunk_angle_deg=angle,
        inside_roi=dist > 0,
        dist_to_roi_edge=dist,
        ankles_outside_roi=ankles_out,
        knees=(k, k),
        ankles=(a, a),
        shoulder_line_angle_deg=0.0,
        velocity=(0.0, 0.0),
        leg_angle_deg=leg_angle,
    )


def posture(f: BodyFeatures, current: S, ref: float | None = None) -> Posture:
    return classify_posture(f, current, ref, CONFIG)


# ---- R3: hysteresis góc thân ----


def test_lying_hysteresis_uses_exit_threshold_while_lying() -> None:
    between = (P.lying_enter_deg + P.lying_exit_deg) / 2
    assert posture(feat(between), S.LYING) == Posture.LYING
    assert posture(feat(P.lying_exit_deg), S.LYING) == Posture.LYING
    assert posture(feat(P.lying_exit_deg + 1), S.LYING) == Posture.RAISING


def test_lying_requires_enter_threshold_when_not_lying() -> None:
    between = (P.lying_enter_deg + P.lying_exit_deg) / 2
    assert posture(feat(between), S.RAISING) == Posture.RAISING
    assert posture(feat(P.lying_enter_deg - 1), S.RAISING) == Posture.LYING
    assert posture(feat(P.lying_enter_deg - 1), S.SITTING) == Posture.LYING


def test_sitting_hysteresis() -> None:
    between = (P.sitting_exit_deg + P.sitting_enter_deg) / 2
    # Chưa ngồi: phải vượt ngưỡng vào
    assert posture(feat(between), S.RAISING) == Posture.RAISING
    assert posture(feat(P.sitting_enter_deg), S.RAISING) == Posture.RAISING
    assert posture(feat(P.sitting_enter_deg + 1), S.RAISING) == Posture.SITTING
    # Đang ngồi (hoặc ở mép giường): chỉ rời khi dưới ngưỡng ra
    assert posture(feat(between), S.SITTING) == Posture.SITTING
    assert posture(feat(P.sitting_exit_deg), S.AT_EDGE) == Posture.SITTING


def test_intermediate_angle_is_raising_only_when_coming_up_from_lying() -> None:
    mid = (P.lying_exit_deg + P.sitting_exit_deg) / 2
    for current in (S.LYING, S.RAISING, S.NO_OBSERVATION):
        assert posture(feat(mid), current) == Posture.RAISING
    # Đang ngồi rồi ngả lưng: góc ở vùng giữa không phải "đang nâng thân" → giữ trạng thái
    assert posture(feat(P.sitting_exit_deg - 1), S.SITTING) == Posture.UNKNOWN


def test_leaving_lying_always_goes_through_raising() -> None:
    assert posture(feat(90), S.LYING) == Posture.RAISING
    standing_legs = feat(90, knee=(0, 60), ankle=(0, 120), leg_angle=90)
    assert posture(standing_legs, S.LYING) == Posture.RAISING


def test_upright_with_shoulder_below_hip_is_unknown() -> None:
    assert posture(feat(80, shoulder_above_hip=False), S.RAISING) == Posture.UNKNOWN


# ---- R3: tỷ lệ torso_length khi camera nhìn dọc trục giường ----


def test_torso_length_ratio_detects_sitting_when_angle_stays_low() -> None:
    change = 1 - P.torso_length_ratio_sitting
    shorter = TORSO * (1 - change - 0.05)
    longer = TORSO * (1 + change + 0.05)
    # Đang nằm: thân co/giãn rõ → bắt đầu nâng thân; đang nâng thân → ngồi
    assert posture(feat(5, torso=shorter), S.LYING, ref=TORSO) == Posture.RAISING
    assert posture(feat(5, torso=shorter), S.RAISING, ref=TORSO) == Posture.SITTING
    assert posture(feat(5, torso=longer), S.RAISING, ref=TORSO) == Posture.SITTING


def test_small_torso_length_change_stays_lying() -> None:
    change = 1 - P.torso_length_ratio_sitting
    assert posture(feat(5, torso=TORSO * (1 - change / 2)), S.LYING, ref=TORSO) == Posture.LYING
    # Chưa có tham chiếu lúc nằm thì không dùng tỷ lệ
    assert posture(feat(5, torso=TORSO / 2), S.LYING, ref=None) == Posture.LYING


# ---- R3: đứng ----

UPRIGHT = 90.0


def test_standing_needs_straight_vertical_legs() -> None:
    f = feat(UPRIGHT, knee=(0, 60), ankle=(0, 120), leg_angle=90)
    assert posture(f, S.AT_EDGE) == Posture.STANDING
    assert posture(f, S.RAISING) == Posture.STANDING


def test_sitting_at_edge_with_hanging_legs_is_not_standing() -> None:
    # Đùi gần nằm ngang: gối chỉ thấp hơn hông chút ít so với cẳng chân
    f = feat(UPRIGHT, dist=0.1, knee=(40, 30), ankle=(40, 130), leg_angle=73)
    assert posture(f, S.SITTING) == Posture.SITTING


def test_horizontal_legs_on_bed_are_not_standing() -> None:
    # Ca suy biến: knee_y ≈ hip_y ≈ ankle_y thỏa tỷ lệ nhưng chân nằm ngang
    f = feat(UPRIGHT, knee=(180, 3), ankle=(360, 5), leg_angle=0.8)
    assert posture(f, S.SITTING) == Posture.SITTING


def test_standing_requires_visible_legs_and_upright_trunk() -> None:
    assert posture(feat(UPRIGHT), S.SITTING) == Posture.SITTING
    lying_legs_down = feat(10, knee=(0, 60), ankle=(0, 120), leg_angle=90)
    assert posture(lying_legs_down, S.LYING) == Posture.LYING


# ---- R4: vị trí ----


def location(f: BodyFeatures, current: S = S.SITTING) -> Location:
    return classify_location(f, current, CONFIG)


def test_location_in_bed_edge_out() -> None:
    assert location(feat(dist=LOC.edge_distance_torso + 0.1)) == Location.IN_BED
    assert location(feat(dist=LOC.edge_distance_torso - 0.05)) == Location.EDGE
    assert location(feat(dist=0.9, ankles_out=1)) == Location.EDGE
    assert location(feat(dist=-LOC.out_of_roi_margin_torso / 2)) == Location.EDGE
    assert location(feat(dist=-LOC.out_of_roi_margin_torso - 0.05)) == Location.OUT


def test_location_hysteresis_return_needs_hip_inside_roi() -> None:
    just_outside = feat(dist=-LOC.out_of_roi_margin_torso / 2)
    assert location(just_outside, S.AT_EDGE) == Location.EDGE
    assert location(just_outside, S.OUT_OF_BED) == Location.OUT
    assert location(feat(dist=0.05), S.OUT_OF_BED) == Location.EDGE
    assert location(feat(dist=0.9), S.OUT_OF_BED) == Location.IN_BED


# ---- R5: ánh xạ sang trạng thái ứng viên ----


@pytest.mark.parametrize(
    ("p", "loc", "expected"),
    [
        (Posture.STANDING, Location.OUT, S.OUT_OF_BED),
        (Posture.LYING, Location.OUT, S.OUT_OF_BED),
        (Posture.UNKNOWN, Location.OUT, S.OUT_OF_BED),
        (Posture.STANDING, Location.EDGE, S.STANDING),
        (Posture.STANDING, Location.IN_BED, S.STANDING),
        (Posture.SITTING, Location.EDGE, S.AT_EDGE),
        (Posture.RAISING, Location.EDGE, S.AT_EDGE),
        (Posture.LYING, Location.EDGE, S.LYING),
        (Posture.SITTING, Location.IN_BED, S.SITTING),
        (Posture.RAISING, Location.IN_BED, S.RAISING),
        (Posture.LYING, Location.IN_BED, S.LYING),
        (Posture.UNKNOWN, Location.IN_BED, None),
        (Posture.UNKNOWN, Location.EDGE, None),
    ],
)
def test_candidate_state_mapping(p: Posture, loc: Location, expected: S | None) -> None:
    assert candidate_state(p, loc) == expected
