"""F36 R11 phía worker: gửi keypoint người mục tiêu (không ảnh) khi phiên có quyền mức SKELETON."""

from postcare.schemas.enums import ObservationQuality
from postcare.schemas.observation import Keypoint, KeypointName, PersonPose
from tests.worker.helpers import default_config, make_harness, snapshot


def _person(x: float) -> PersonPose:
    return PersonPose(
        keypoints={
            KeypointName.NOSE: Keypoint(x=x, y=0.3, visibility=0.9),
            KeypointName.LEFT_HIP: Keypoint(x=x, y=0.6, visibility=0.8),
        }
    )


def test_no_keypoints_when_not_shared() -> None:
    h = make_harness(persons=lambda i: [_person(0.5)])
    h.run_until(3.0)
    states = h.api.paths("/state")
    assert states  # trạng thái vẫn gửi như cũ
    assert all("target_keypoints" not in c[3] for c in states)
    assert len(states) <= 2


def test_keypoints_sent_about_5_per_second_when_shared() -> None:
    h = make_harness(persons=lambda i: [_person(0.5)], config=default_config(share_skeleton=True))
    h.run_until(4.0)
    with_kp = [c for c in h.api.paths("/state") if "target_keypoints" in c[3]]
    assert 15 <= len(with_kp) <= 22, len(with_kp)
    kp = with_kp[-1][3]["target_keypoints"]
    assert kp == {"nose": [0.5, 0.3, 0.9], "left_hip": [0.5, 0.6, 0.8]}
    for c in with_kp:
        assert set(c[3]) == {
            "body_state",
            "observation_quality",
            "activity_level",
            "rest_status",
            "face_status",
            "face_signals",
            "ts",
            "target_keypoints",
        }


def test_keypoints_null_when_multiple_people() -> None:
    h = make_harness(
        persons=lambda i: [_person(0.4), _person(0.6)],
        config=default_config(share_skeleton=True),
    )
    multi = snapshot().model_copy(
        update={"observation_quality": ObservationQuality.MULTIPLE_PEOPLE}
    )

    def _process(obs):  # engine giả báo nhiều người
        from postcare.schemas.events import EngineOutput

        return EngineOutput(state=multi, state_changed=obs.frame_index == 0)

    h.run_until(0.1)
    h.engines[0].process = _process  # type: ignore[method-assign]
    h.run_until(2.0)
    later = [c for c in h.api.paths("/state") if c[0] > 100.2 and "target_keypoints" in c[3]]
    assert later
    assert all(c[3]["target_keypoints"] is None for c in later)


def test_no_keypoints_while_paused() -> None:
    h = make_harness(
        persons=lambda i: [_person(0.5)],
        config=default_config(share_skeleton=True, capture_paused=True),
    )
    h.run_until(3.0)
    assert h.api.paths("/state") == []
    assert h.api.paths("/frame") == []
