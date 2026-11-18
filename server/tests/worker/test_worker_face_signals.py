"""F26: tín hiệu mặt do engine suy ra đi vào body `POST /internal/v1/cameras/{id}/state`."""

from datetime import UTC, datetime

from postcare.schemas.enums import FaceStatus
from postcare.worker.loop import _state_body
from tests.engine.builders import PoseSequence, run_engine
from tests.engine.face_builders import ON, face, with_face


def test_state_body_carries_face_signals() -> None:
    frames = with_face(
        PoseSequence(fps=15).lying(seconds=9).build(),
        [face(seconds=6), face({"brow_down": ON, "eye_squint": ON}, seconds=3)],
    )
    state = run_engine(frames)[-1].state
    body = _state_body(state, datetime(2026, 11, 18, tzinfo=UTC))
    assert body["face_status"] == FaceStatus.OK.value
    assert body["face_signals"]["brow_down"] is True
    assert body["face_signals"]["eye_squint"] is True
    assert body["face_signals"]["eyes_closed"] is False
