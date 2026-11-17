"""F16 AC2, R4: ghép dự đoán với ground truth có tolerance (A06: [start − 1 s, end + 3 s])."""

from postcare.eval.manifest import TruthRow
from postcare.eval.matching import match_events
from postcare.schemas.events import EventCode
from tests.eval.helpers import pred

BED_EXIT = EventCode.BED_EXIT
SIT_UP = EventCode.SIT_UP


def truth(code: EventCode, start: float, end: float, video_id: str = "v1") -> TruthRow:
    return TruthRow(video_id=video_id, event_code=code, start_s=start, end_s=end)


def test_prediction_inside_tolerance_is_tp() -> None:
    gt = [truth(BED_EXIT, 20.0, 25.0)]
    for t in (19.0, 20.0, 22.0, 25.0, 28.0):  # hai biên tính là trong
        r = match_events([pred(BED_EXIT, t)], gt)
        assert (len(r.tp), len(r.fp), len(r.fn)) == (1, 0, 0), t
        assert r.tp[0].truth == gt[0]


def test_prediction_outside_tolerance_is_fp_and_fn() -> None:
    gt = [truth(BED_EXIT, 20.0, 25.0)]
    for t in (18.99, 28.01):
        r = match_events([pred(BED_EXIT, t)], gt)
        assert (len(r.tp), len(r.fp), len(r.fn)) == (0, 1, 1), t


def test_wrong_code_is_fp_and_fn() -> None:
    r = match_events([pred(SIT_UP, 21.0)], [truth(BED_EXIT, 20.0, 25.0)])
    assert (len(r.tp), len(r.fp), len(r.fn)) == (0, 1, 1)
    assert r.fp[0].code == SIT_UP
    assert r.fn[0].event_code == BED_EXIT


def test_two_predictions_one_truth_gives_one_tp_one_fp() -> None:
    r = match_events([pred(BED_EXIT, 21.0), pred(BED_EXIT, 22.0)], [truth(BED_EXIT, 20.0, 25.0)])
    assert (len(r.tp), len(r.fp), len(r.fn)) == (1, 1, 0)


def test_custom_tolerance() -> None:
    gt = [truth(BED_EXIT, 20.0, 20.0)]
    p = [pred(BED_EXIT, 24.5)]
    assert len(match_events(p, gt).tp) == 0  # mặc định end + 3 s
    assert len(match_events(p, gt, tol_before_s=0.0, tol_after_s=5.0).tp) == 1
    p_before = [pred(BED_EXIT, 18.5)]
    assert len(match_events(p_before, gt, tol_before_s=2.0).tp) == 1
    assert len(match_events(p_before, gt, tol_before_s=0.5).tp) == 0


def test_greedy_nearest_pairing() -> None:
    """Hai ground truth gần nhau: mỗi dự đoán ghép với truth gần nhất, không ai bị ghép hai lần."""
    gt = [truth(SIT_UP, 10.0, 10.0), truth(SIT_UP, 12.0, 12.0)]
    r = match_events([pred(SIT_UP, 11.8), pred(SIT_UP, 10.1)], gt)
    assert len(r.tp) == 2
    pairs = {m.truth.start_s: m.prediction.occurred_s for m in r.tp}
    assert pairs == {10.0: 10.1, 12.0: 11.8}


def test_unlisted_code_not_counted_as_fp() -> None:
    """Dữ liệu ngoài: mã không thuộc `eval_codes` của video bị bỏ qua (không FP)."""
    r = match_events(
        [pred(BED_EXIT, 3.0), pred(EventCode.ABNORMAL_MOVEMENT, 2.5)],
        [truth(EventCode.ABNORMAL_MOVEMENT, 2.0, 3.0)],
        eval_codes=frozenset({EventCode.ABNORMAL_MOVEMENT}),
    )
    assert (len(r.tp), len(r.fp), len(r.fn)) == (1, 0, 0)
    assert [p.code for p in r.ignored] == [BED_EXIT]


def test_no_eval_codes_scores_every_code() -> None:
    r = match_events([pred(BED_EXIT, 3.0)], [], eval_codes=None)
    assert len(r.fp) == 1
