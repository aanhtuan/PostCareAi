"""F10 AC1: schema quan sát chung, JSON round-trip và kiểm tra miền giá trị."""

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from postcare.schemas.context import EngineContext
from postcare.schemas.enums import (
    ActivityLevel,
    BodyState,
    FaceStatus,
    ObservationQuality,
    Priority,
    RestStatus,
)
from postcare.schemas.events import EngineEvent, EngineOutput, EventCode
from postcare.schemas.observation import (
    FaceObservation,
    FrameObservation,
    Keypoint,
    KeypointName,
    PersonPose,
)
from postcare.schemas.roi import RoiPolygon
from postcare.schemas.state import BodyStateSnapshot, FaceSignals

EXPECTED_KEYPOINTS = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
]


def _person() -> PersonPose:
    return PersonPose(
        keypoints={
            KeypointName.LEFT_SHOULDER: Keypoint(x=0.40, y=0.30, visibility=0.9),
            KeypointName.RIGHT_SHOULDER: Keypoint(x=0.55, y=0.31, visibility=0.8),
            KeypointName.LEFT_HIP: Keypoint(x=0.42, y=0.60, visibility=0.7),
            KeypointName.RIGHT_HIP: Keypoint(x=0.0, y=1.0, visibility=0.0),
        }
    )


def _frame() -> FrameObservation:
    return FrameObservation(
        camera_id=1,
        frame_index=42,
        ts_ms=2800,
        image_size=(1280, 720),
        persons=[_person(), _person()],
        face=FaceObservation(
            status=FaceStatus.OK,
            head_box_px=120,
            blendshapes={"eyeBlinkLeft": 0.7, "browDownLeft": 0.1},
        ),
        source_ok=True,
    )


def _snapshot() -> BodyStateSnapshot:
    return BodyStateSnapshot(
        body_state=BodyState.SITTING,
        observation_quality=ObservationQuality.GOOD,
        activity_level=ActivityLevel.NORMAL,
        rest_status=RestStatus.ACTIVE,
        face_status=FaceStatus.OK,
        face_signals=FaceSignals(eyes_closed=True, brow_down=True),
    )


def _event(**kw: Any) -> EngineEvent:
    data: dict[str, Any] = {
        "code": EventCode.SIT_UP,
        "priority": Priority.INFO,
        "occurred_at_ms": 1000,
        "detected_at_ms": 3000,
        "confidence": 0.8,
        "observation_quality": ObservationQuality.GOOD,
        "explanation": {"rule_id": "body.sit_up", "trunk_angle_deg": 62.5, "path": ["LYING"]},
    }
    data.update(kw)
    return EngineEvent(**data)


def _roundtrip[M: BaseModel](obj: M) -> M:
    return type(obj).model_validate_json(obj.model_dump_json())


# --------------------------------------------------------------------------- round-trip


def test_keypoint_names_are_model_neutral() -> None:
    assert [k.value for k in KeypointName] == EXPECTED_KEYPOINTS


def test_frame_observation_roundtrip() -> None:
    obs = _frame()
    assert _roundtrip(obs) == obs
    empty = FrameObservation(
        camera_id=2, frame_index=0, ts_ms=0, image_size=(640, 480), persons=[], source_ok=False
    )
    assert empty.face is None
    assert _roundtrip(empty) == empty


def test_frame_observation_json_uses_neutral_names() -> None:
    js = _frame().model_dump_json()
    assert '"left_shoulder"' in js
    assert '"image_size":[1280,720]' in js


def test_engine_output_roundtrip() -> None:
    out = EngineOutput(state=_snapshot(), state_changed=True, events=[_event()])
    assert _roundtrip(out) == out
    assert out.events[0].explanation["rule_id"] == "body.sit_up"


def test_other_schemas_roundtrip() -> None:
    roi = RoiPolygon(points=[(0.2, 0.25), (0.8, 0.25), (0.8, 0.85), (0.2, 0.85)])
    objs: list[BaseModel] = [
        _person(),
        FaceObservation(status=FaceStatus.TOO_SMALL, head_box_px=40, blendshapes={}),
        FaceSignals(),
        _snapshot(),
        _event(),
        roi,
        EngineContext(camera_id=1, roi_polygon=roi),
    ]
    for obj in objs:
        assert _roundtrip(obj) == obj, type(obj).__name__


def test_face_signals_default_false() -> None:
    sig = FaceSignals()
    assert not any(sig.model_dump().values())
    assert set(sig.model_dump()) == {
        "eyes_closed",
        "eyes_closed_prolonged",
        "brow_down",
        "eye_squint",
        "nose_sneer",
        "mouth_change",
    }


def test_schemas_are_frozen() -> None:
    obs = _frame()
    with pytest.raises(ValidationError):
        obs.ts_ms = 1  # type: ignore[misc]


# --------------------------------------------------------------------------- ca âm tính


@pytest.mark.parametrize(
    "kw",
    [
        {"x": -0.01, "y": 0.5, "visibility": 0.5},
        {"x": 1.01, "y": 0.5, "visibility": 0.5},
        {"x": 0.5, "y": 1.5, "visibility": 0.5},
        {"x": 0.5, "y": 0.5, "visibility": -0.1},
        {"x": 0.5, "y": 0.5, "visibility": 1.2},
    ],
)
def test_keypoint_rejects_out_of_range(kw: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        Keypoint(**kw)


def test_unknown_keypoint_name_rejected() -> None:
    with pytest.raises(ValidationError):
        PersonPose.model_validate({"keypoints": {"left_toe": {"x": 0, "y": 0, "visibility": 1}}})
    # Tên riêng của MediaPipe (chỉ số landmark) không được lọt vào schema chung
    with pytest.raises(ValidationError):
        PersonPose.model_validate({"keypoints": {"11": {"x": 0, "y": 0, "visibility": 1}}})


def test_frame_observation_rejects_bad_values() -> None:
    base = _frame().model_dump()
    for field, value in [("image_size", (0, 720)), ("frame_index", -1), ("ts_ms", -5)]:
        with pytest.raises(ValidationError):
            FrameObservation.model_validate({**base, field: value})


def test_face_observation_rejects_bad_values() -> None:
    with pytest.raises(ValidationError):
        FaceObservation(status=FaceStatus.OK, head_box_px=100, blendshapes={"eyeBlinkLeft": 1.5})
    with pytest.raises(ValidationError):
        FaceObservation.model_validate(
            {"status": "SLEEPING", "head_box_px": 100, "blendshapes": {}}
        )


def test_event_requires_rule_id() -> None:
    with pytest.raises(ValidationError, match="rule_id"):
        _event(explanation={"trunk_angle_deg": 60})
    with pytest.raises(ValidationError, match="rule_id"):
        _event(explanation={"rule_id": ""})


def test_event_priority_must_be_allowed_for_code() -> None:
    with pytest.raises(ValidationError, match="priority"):
        _event(code=EventCode.BED_EXIT, priority=Priority.INFO)
    assert _event(code=EventCode.FACE_ATTENTION, priority=Priority.HIGH).priority == Priority.HIGH


def test_event_rejects_bad_times_and_confidence() -> None:
    with pytest.raises(ValidationError):
        _event(occurred_at_ms=5000, detected_at_ms=3000)
    with pytest.raises(ValidationError):
        _event(confidence=1.5)


def test_roi_polygon_rejects_bad_points() -> None:
    with pytest.raises(ValidationError):
        RoiPolygon(points=[(0.1, 0.1), (0.9, 0.1)])
    with pytest.raises(ValidationError):
        RoiPolygon(points=[(0.1, 0.1), (1.2, 0.1), (0.5, 0.9)])
