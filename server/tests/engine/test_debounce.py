"""F15 AC4: debounce cùng `code` trong `debounce.same_code_same_session_s`.

A01; event-engine.md mục 7.
"""

from itertools import pairwise

from postcare.engine.debounce import Debouncer

from postcare.schemas.state import BodyState as S
from tests.engine.builders import AT_EDGE, SITTING, codes, default_config, run_engine
from tests.engine.test_rules_body import at_edge_established

CONFIG = default_config()
MIN = CONFIG.min_duration_s
WINDOW_S = CONFIG.debounce.same_code_same_session_s


def test_debouncer_blocks_same_key_within_window() -> None:
    d = Debouncer(window_s=60)
    assert d.allow("BED_EDGE", 1_000)
    assert not d.allow("BED_EDGE", 1_000 + 59_999)
    assert d.allow("BED_EDGE", 1_000 + 60_000)


def test_debouncer_keys_independent() -> None:
    d = Debouncer(window_s=60)
    assert d.allow("BED_EDGE", 0)
    assert d.allow("BED_EXIT", 10)
    assert not d.allow("BED_EDGE", 20)


def test_debouncer_window_counts_from_last_emitted() -> None:
    """Lần bị chặn không dời mốc: tính từ lần **phát** gần nhất."""
    d = Debouncer(window_s=60)
    assert d.allow("X", 0)
    assert not d.allow("X", 50_000)
    assert d.allow("X", 60_000)
    assert not d.allow("X", 100_000)


def test_debouncer_zero_window_never_blocks() -> None:
    d = Debouncer(window_s=0)
    assert d.allow("X", 0)
    assert d.allow("X", 1)


def edge_again(builder_seconds_between: float) -> list[str]:
    """Vào mép → về ngồi giữa giường (chờ thêm) → vào mép lần nữa."""
    seq = (
        at_edge_established()
        .move_to(SITTING, seconds=1)
        .sitting(seconds=builder_seconds_between)
        .move_to_edge(seconds=1)
        .pose(AT_EDGE, seconds=MIN.AT_EDGE + 1)
        .build()
    )
    outs = run_engine(seq)
    states = [o.state.body_state for o in outs]
    # Đúng là vào AT_EDGE hai lần
    entries = sum(1 for a, b in pairwise(states) if b == S.AT_EDGE != a)
    assert entries == 2
    return codes(outs)


def test_same_code_within_window_emitted_once() -> None:
    assert edge_again(MIN.SITTING + 1).count("BED_EDGE") == 1


def test_same_code_after_window_and_reentry_emitted_again() -> None:
    assert edge_again(WINDOW_S + 1).count("BED_EDGE") == 2


def test_staying_in_state_does_not_repeat_event() -> None:
    """Chỉ phát khi **vào** trạng thái: ở yên AT_EDGE quá cửa sổ debounce không phát lại."""
    seq = at_edge_established().hold(seconds=WINDOW_S * 2 + 5).build()
    assert codes(run_engine(seq)).count("BED_EDGE") == 1
