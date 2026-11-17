"""F11 AC2 (R4, R6): ánh xạ 33 landmark MediaPipe → `KeypointName` trung lập, không cần model."""

import pytest

from postcare.schemas import observation as schema_observation
from postcare.schemas.observation import Keypoint, KeypointName, PersonPose
from postcare.vision.inference.mapping import (
    MEDIAPIPE_LANDMARK_COUNT,
    MEDIAPIPE_POSE_INDEX,
    landmarks_to_person,
)

# Chỉ số theo tài liệu MediaPipe Pose Landmarker (33 điểm).
EXPECTED_INDEX = {
    "nose": 0,
    "left_eye": 2,
    "right_eye": 5,
    "left_ear": 7,
    "right_ear": 8,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
    "left_heel": 29,
    "right_heel": 30,
    "left_foot_index": 31,
    "right_foot_index": 32,
}

Landmark = tuple[float, float, float | None]


def _landmarks() -> list[Landmark]:
    """Landmark thứ i có x = i/100, y = 1 − i/100, visibility = 0.5 + i/100 (dễ nhận ra)."""
    return [(i / 100, 1 - i / 100, 0.5 + i / 100) for i in range(MEDIAPIPE_LANDMARK_COUNT)]


def test_mapping_mediapipe_to_keypoint_names() -> None:
    assert MEDIAPIPE_LANDMARK_COUNT == 33
    assert {k.value: v for k, v in MEDIAPIPE_POSE_INDEX.items()} == EXPECTED_INDEX
    person = landmarks_to_person(_landmarks())
    assert isinstance(person, PersonPose)
    assert set(person.keypoints) == set(KeypointName)
    for name, idx in EXPECTED_INDEX.items():
        kp = person.keypoints[KeypointName(name)]
        assert kp == Keypoint(x=idx / 100, y=1 - idx / 100, visibility=0.5 + idx / 100)


def test_mapping_clamps_coordinates() -> None:
    lms = _landmarks()
    nose = MEDIAPIPE_POSE_INDEX[KeypointName.NOSE]
    l_sh = MEDIAPIPE_POSE_INDEX[KeypointName.LEFT_SHOULDER]
    r_sh = MEDIAPIPE_POSE_INDEX[KeypointName.RIGHT_SHOULDER]
    lms[nose] = (-0.2, 1.3, 0.9)
    lms[l_sh] = (1.7, -0.01, 1.2)  # visibility ngoài [0, 1] cũng kẹp
    lms[r_sh] = (0.4, 0.6, -0.5)
    person = landmarks_to_person(lms)
    assert person.keypoints[KeypointName.NOSE] == Keypoint(x=0.0, y=1.0, visibility=0.9)
    assert person.keypoints[KeypointName.LEFT_SHOULDER] == Keypoint(x=1.0, y=0.0, visibility=1.0)
    assert person.keypoints[KeypointName.RIGHT_SHOULDER] == Keypoint(x=0.4, y=0.6, visibility=0.0)


def test_mapping_treats_missing_visibility_as_zero() -> None:
    lms = _landmarks()
    lms[0] = (0.5, 0.5, None)
    person = landmarks_to_person(lms)
    assert person.keypoints[KeypointName.NOSE].visibility == 0.0


@pytest.mark.parametrize("count", [0, 17, 32, 34])
def test_mapping_rejects_wrong_landmark_count(count: int) -> None:
    with pytest.raises(ValueError, match="33"):
        landmarks_to_person([(0.5, 0.5, 1.0)] * count)


def test_mapping_rejects_non_finite_values() -> None:
    lms = _landmarks()
    lms[11] = (float("nan"), 0.5, 1.0)
    with pytest.raises(ValueError, match="11"):
        landmarks_to_person(lms)


def test_mapping_output_uses_schema_types_only() -> None:
    person = landmarks_to_person(_landmarks())
    assert type(person) is schema_observation.PersonPose
    for name, kp in person.keypoints.items():
        assert type(name) is KeypointName
        assert type(kp) is schema_observation.Keypoint
