"""F23 AC1 và R4: chỉ số vận động trên cửa sổ trượt và `activity_level` (event-engine.md mục 5).

Chuỗi chạy qua `Engine` (làm mượt, cổng chất lượng) trên `PoseSequence`. Tốc độ cử động trong test
tính từ ngưỡng của `engine.default.yaml`, không viết cứng ngưỡng.
"""

import pytest

from postcare.engine import Engine
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.events import EngineOutput
from postcare.schemas.state import ActivityLevel as A
from postcare.schemas.state import BodyState as S
from tests.engine.builders import (
    PoseSequence,
    context,
    default_config,
)

CONFIG = default_config()
ACT = CONFIG.activity
RESTORE = CONFIG.quality.restore_duration_s
LOST = CONFIG.quality.low_quality_to_no_observation_s
FPS = 15
FILL_S = ACT.sample_interval_s + ACT.window_s
"""Từ lúc có quan sát tới khi cửa sổ vận động đủ dữ liệu: mẫu đầu cần một bước đo."""
SETTLE_S = RESTORE + FILL_S + 1
"""Đủ để cổng chất lượng mở và cửa sổ vận động được lấp đầy."""
MODERATE = (ACT.low_threshold + ACT.high_threshold) / 2
VIGOROUS = 3 * ACT.high_threshold


def run(seq: PoseSequence, config: EngineConfig = CONFIG) -> tuple[Engine, list[EngineOutput]]:
    engine = Engine(config, context())
    outs = [engine.process(obs) for obs in seq.build()]
    return engine, outs


def last_level(outs: list[EngineOutput]) -> A:
    return outs[-1].state.activity_level


def test_still_body_is_low() -> None:
    engine, outs = run(PoseSequence(fps=FPS).lying(seconds=SETTLE_S))
    assert last_level(outs) == A.LOW
    assert engine.activity_index is not None
    assert engine.activity_index < ACT.low_threshold


def test_moderate_motion_is_normal() -> None:
    # Cả thân dao động nhẹ tại chỗ: tốc độ keypoint ở giữa hai ngưỡng
    seq = PoseSequence(fps=FPS).lying(seconds=RESTORE + 0.5)
    seq.limb_motion(seconds=FILL_S + 2, speed_torso_per_s=MODERATE, whole_body=True)
    engine, outs = run(seq)
    assert last_level(outs) == A.NORMAL
    assert engine.activity_index is not None
    assert ACT.low_threshold <= engine.activity_index <= ACT.high_threshold


def test_vigorous_motion_is_high() -> None:
    seq = PoseSequence(fps=FPS).lying(seconds=RESTORE + 0.5)
    seq.limb_motion(seconds=FILL_S + 2, speed_torso_per_s=VIGOROUS, whole_body=True)
    engine, outs = run(seq)
    assert last_level(outs) == A.HIGH
    assert engine.activity_index is not None
    assert engine.activity_index > ACT.high_threshold


def test_leg_motion_only_counts_partially() -> None:
    """Chỉ gối và cổ chân cử động: chỉ số là trung bình trên mọi keypoint thấy được, nên thấp hơn
    tốc độ của chân (một nửa số keypoint của builder di chuyển)."""
    seq = PoseSequence(fps=FPS).lying(seconds=RESTORE + 0.5)
    seq.limb_motion(seconds=FILL_S + 2, speed_torso_per_s=VIGOROUS)
    engine, _ = run(seq)
    assert engine.activity_index is not None
    assert engine.activity_index < VIGOROUS
    assert engine.activity_index > ACT.low_threshold


@pytest.mark.parametrize("factor", [0.5, 1.5])
def test_index_invariant_to_body_scale(factor: float) -> None:
    def index(scale: float) -> float:
        seq = PoseSequence(fps=FPS).scaled(scale).hold(RESTORE + 0.5)
        seq.limb_motion(seconds=FILL_S + 2, speed_torso_per_s=MODERATE, whole_body=True)
        engine, _ = run(seq)
        assert engine.activity_index is not None
        return engine.activity_index

    assert index(factor) == pytest.approx(index(1.0), rel=0.05)


def test_window_not_filled_is_unknown() -> None:
    _, outs = run(PoseSequence(fps=FPS).lying(seconds=RESTORE + FILL_S / 2))
    assert last_level(outs) == A.UNKNOWN


@pytest.mark.parametrize("mode", ["low_visibility", "missing"])
def test_no_observation_gives_unknown_not_low(mode: str) -> None:
    seq = PoseSequence(fps=FPS).lying(seconds=SETTLE_S).drop_landmarks(seconds=LOST + 30, mode=mode)
    engine, outs = run(seq)
    lost = [o for o in outs if o.state.body_state == S.NO_OBSERVATION]
    assert lost, "phải vào NO_OBSERVATION"
    tail = outs[-FPS * 10 :]
    assert {o.state.activity_level for o in tail} == {A.UNKNOWN}
    assert engine.activity_index is None


def test_activity_resets_after_no_observation() -> None:
    """Sau khi quan sát lại: cửa sổ được lấp lại từ đầu, chưa đủ dữ liệu thì UNKNOWN (R4)."""
    seq = (
        PoseSequence(fps=FPS)
        .lying(seconds=SETTLE_S)
        .drop_landmarks(seconds=LOST + 1, mode="missing")
        .lying(seconds=RESTORE + FILL_S / 2)
    )
    _, outs = run(seq)
    assert last_level(outs) == A.UNKNOWN


def test_activity_level_in_snapshot_changes_state() -> None:
    """R11: activity_level đi trong BodyStateSnapshot; đổi mức → state_changed."""
    _, outs = run(PoseSequence(fps=FPS).lying(seconds=SETTLE_S))
    levels = [o.state.activity_level for o in outs]
    first_low = levels.index(A.LOW)
    assert outs[first_low].state_changed
    assert all(lv == A.UNKNOWN for lv in levels[:first_low])


def test_activity_deterministic() -> None:
    seq = PoseSequence(fps=FPS).lying(seconds=RESTORE + 0.5)
    seq.limb_motion(seconds=FILL_S + 2, speed_torso_per_s=MODERATE)
    _, first = run(seq)
    _, second = run(seq)
    assert [o.model_dump_json() for o in first] == [o.model_dump_json() for o in second]
