"""Bước 4: tư thế và vị trí thô của người mục tiêu (F14 R3–R5; event-engine.md mục 4, mục 6).

Hàm thuần, không giữ trạng thái: hysteresis dựa vào trạng thái ổn định hiện tại do state machine
truyền vào. Mọi ngưỡng lấy từ `EngineConfig` (`posture.*`, `location.*`).
"""

from enum import StrEnum

from postcare.engine.features import BodyFeatures
from postcare.engine.geometry import Px
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.state import BodyState


class Posture(StrEnum):
    LYING = "LYING"
    RAISING = "RAISING"
    SITTING = "SITTING"
    STANDING = "STANDING"
    UNKNOWN = "UNKNOWN"


class Location(StrEnum):
    IN_BED = "IN_BED"
    EDGE = "EDGE"
    OUT = "OUT"


UPRIGHT_STATES = frozenset(
    {BodyState.SITTING, BodyState.AT_EDGE, BodyState.STANDING, BodyState.OUT_OF_BED}
)
"""Trạng thái có thân thẳng: rời "thân thẳng" chỉ khi góc < `sitting_exit_deg` *(giả định)*."""

RISING_STATES = frozenset({BodyState.LYING, BodyState.RAISING, BodyState.NO_OBSERVATION})
"""Góc ở vùng giữa chỉ là `RAISING` khi đi lên từ nằm (PDF §7.1) *(giả định cho NO_OBSERVATION)*."""

LEG_STATES = frozenset({BodyState.STANDING, BodyState.OUT_OF_BED})


def _is_upright_angle(angle: float, upright_now: bool, config: EngineConfig) -> bool:
    p = config.posture
    return angle >= p.sitting_exit_deg if upright_now else angle > p.sitting_enter_deg


def torso_ratio_changed(features: BodyFeatures, ref_torso: float | None, cfg: EngineConfig) -> bool:
    """`|torso / torso_lúc_nằm − 1| ≥ 1 − torso_length_ratio_sitting` (event-engine.md mục 6)."""
    if ref_torso is None or ref_torso <= 0:
        return False
    change = abs(features.torso_length / ref_torso - 1)
    return change >= 1 - cfg.posture.torso_length_ratio_sitting


def _mean_y(points: tuple[Px | None, Px | None]) -> float | None:
    ys = [p[1] for p in points if p is not None]
    return sum(ys) / len(ys) if ys else None


def _legs_standing(features: BodyFeatures, current: BodyState, config: EngineConfig) -> bool:
    """Chân duỗi thẳng đứng: gối dưới hông, cổ chân dưới gối, tỷ lệ đùi/cẳng chân và vector
    hông → cổ chân thẳng theo cùng ngưỡng góc của thân *(giả định F14)*. y hướng xuống."""
    knee_y = _mean_y(features.knees)
    ankle_y = _mean_y(features.ankles)
    if knee_y is None or ankle_y is None or features.leg_angle_deg is None:
        return False
    hip_y = features.hip_center[1]
    thigh = knee_y - hip_y
    shin = ankle_y - knee_y
    if thigh <= 0 or shin <= 0:
        return False
    if thigh < config.posture.standing_hip_above_knee_ratio * shin:
        return False
    return _is_upright_angle(features.leg_angle_deg, current in LEG_STATES, config)


def classify_posture(
    features: BodyFeatures,
    current: BodyState,
    ref_torso: float | None,
    config: EngineConfig,
) -> Posture:
    """Tư thế thô có hysteresis theo trạng thái ổn định `current` (F14 R3)."""
    p = config.posture
    angle = features.trunk_angle_deg
    upright = _is_upright_angle(angle, current in UPRIGHT_STATES, config)
    lying_zone = (
        angle <= p.lying_exit_deg if current == BodyState.LYING else angle < p.lying_enter_deg
    )
    if lying_zone and torso_ratio_changed(features, ref_torso, config):
        # Góc 2D báo nằm nhưng thân co/giãn rõ: camera nhìn dọc trục giường (mục 6)
        upright = True
    if upright and current == BodyState.LYING:
        # Rời LYING luôn qua RAISING: LYING → RAISING → SITTING (PDF §7.1) *(giả định F14)*
        return Posture.RAISING
    if upright:
        if features.shoulder_center[1] >= features.hip_center[1]:
            return Posture.UNKNOWN  # vai không cao hơn hông: không đủ căn cứ là ngồi/đứng
        if _legs_standing(features, current, config):
            return Posture.STANDING
        return Posture.SITTING
    if lying_zone:
        return Posture.LYING
    return Posture.RAISING if current in RISING_STATES else Posture.UNKNOWN


def classify_location(features: BodyFeatures, current: BodyState, config: EngineConfig) -> Location:
    """Vị trí thô (F14 R4). Đang `OUT_OF_BED` thì chỉ quay vào khi tâm hông vào trong ROI."""
    loc = config.location
    dist = features.dist_to_roi_edge
    out = (
        not features.inside_roi
        if current == BodyState.OUT_OF_BED
        else (dist < -loc.out_of_roi_margin_torso)
    )
    if out:
        return Location.OUT
    if dist < loc.edge_distance_torso or features.ankles_outside_roi >= 1:
        return Location.EDGE
    return Location.IN_BED


_SAME_NAME = {
    Posture.LYING: BodyState.LYING,
    Posture.RAISING: BodyState.RAISING,
    Posture.SITTING: BodyState.SITTING,
}


def candidate_state(posture: Posture, location: Location) -> BodyState | None:
    """Trạng thái ứng viên theo thứ tự R5; `None` = giữ trạng thái hiện tại (tư thế UNKNOWN)."""
    if location == Location.OUT:
        return BodyState.OUT_OF_BED
    if posture == Posture.STANDING:
        return BodyState.STANDING
    if posture in (Posture.SITTING, Posture.RAISING) and location == Location.EDGE:
        return BodyState.AT_EDGE
    return _SAME_NAME.get(posture)
