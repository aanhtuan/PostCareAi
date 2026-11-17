"""F11 R8: `FakePoseAdapter` trả quan sát dựng sẵn theo `frame_index` (cho test worker/replay)."""

import numpy as np

from postcare.schemas.observation import FrameObservation, Keypoint, KeypointName, PersonPose
from postcare.vision.camera import Frame
from postcare.vision.inference.base import PoseAdapter
from postcare.vision.inference.fake import FakePoseAdapter

PERSON = PersonPose(keypoints={KeypointName.NOSE: Keypoint(x=0.5, y=0.2, visibility=0.9)})


def _frame(index: int, ts_ms: int) -> Frame:
    return Frame(image=np.zeros((48, 64, 3), dtype=np.uint8), ts_ms=ts_ms, frame_index=index)


def test_fake_adapter_returns_prepared_persons_by_frame_index() -> None:
    adapter: PoseAdapter = FakePoseAdapter({1: [PERSON], 2: [PERSON, PERSON]})
    obs = [adapter.observe(_frame(i, 100 * i), camera_id=7) for i in range(3)]
    assert all(isinstance(o, FrameObservation) for o in obs)
    assert [len(o.persons) for o in obs] == [0, 1, 2]
    assert obs[1].persons[0] == PERSON
    assert obs[2].camera_id == 7
    assert obs[2].frame_index == 2
    assert obs[2].ts_ms == 200
    assert obs[2].image_size == (64, 48)
    assert all(o.source_ok and o.face is None for o in obs)


def test_fake_adapter_records_calls_and_close() -> None:
    adapter = FakePoseAdapter({})
    adapter.observe(_frame(0, 0), camera_id=1)
    adapter.observe(_frame(1, 33), camera_id=1)
    assert adapter.calls == [0, 1]
    assert not adapter.closed
    adapter.close()
    assert adapter.closed
