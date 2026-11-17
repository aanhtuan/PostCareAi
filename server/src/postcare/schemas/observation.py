"""Schema chung giữa adapter AI và Event Engine (event-engine.md mục 2; PDF §10).

Adapter (MediaPipe, RTMPose…) chuyển output model sang các kiểu này. Engine chỉ đọc các kiểu này,
nên đổi model thì chỉ adapter đổi (HS §6.1). Đây cũng là định dạng dòng của `observations.jsonl`.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from postcare.schemas.enums import FaceStatus

UnitFloat = Annotated[float, Field(ge=0.0, le=1.0)]
"""Số thực trong [0, 1]: toạ độ chuẩn hóa theo khung hình, visibility, điểm blendshape."""


class KeypointName(StrEnum):
    """Tên keypoint trung lập với model (F10 R3, giả định: 17 điểm COCO + gót + mũi bàn chân).

    Giá trị viết thường, khớp `pose.required_keypoints` trong `config/engine.default.yaml`.
    """

    NOSE = "nose"
    LEFT_EYE = "left_eye"
    RIGHT_EYE = "right_eye"
    LEFT_EAR = "left_ear"
    RIGHT_EAR = "right_ear"
    LEFT_SHOULDER = "left_shoulder"
    RIGHT_SHOULDER = "right_shoulder"
    LEFT_ELBOW = "left_elbow"
    RIGHT_ELBOW = "right_elbow"
    LEFT_WRIST = "left_wrist"
    RIGHT_WRIST = "right_wrist"
    LEFT_HIP = "left_hip"
    RIGHT_HIP = "right_hip"
    LEFT_KNEE = "left_knee"
    RIGHT_KNEE = "right_knee"
    LEFT_ANKLE = "left_ankle"
    RIGHT_ANKLE = "right_ankle"
    LEFT_HEEL = "left_heel"
    RIGHT_HEEL = "right_heel"
    LEFT_FOOT_INDEX = "left_foot_index"
    RIGHT_FOOT_INDEX = "right_foot_index"


class Keypoint(BaseModel):
    """Một keypoint: x, y chuẩn hóa theo khung hình (y hướng xuống), visibility ∈ [0, 1].

    Adapter phải kẹp toạ độ nằm ngoài khung về [0, 1] (và hạ visibility) trước khi tạo.
    """

    model_config = ConfigDict(frozen=True)

    x: UnitFloat
    y: UnitFloat
    visibility: UnitFloat


class PersonPose(BaseModel):
    """Tư thế một người. Keypoint không phát hiện được thì không có trong dict."""

    model_config = ConfigDict(frozen=True)

    keypoints: dict[KeypointName, Keypoint]


class FaceObservation(BaseModel):
    """Output của adapter khuôn mặt (F25). `blendshapes` chỉ gồm các khóa trong `face.signals`."""

    model_config = ConfigDict(frozen=True)

    status: FaceStatus
    head_box_px: Annotated[int, Field(ge=0)]
    blendshapes: dict[str, UnitFloat]


class FrameObservation(BaseModel):
    """Toàn bộ quan sát của một khung hình, đầu vào duy nhất của `Engine.process`."""

    model_config = ConfigDict(frozen=True)

    camera_id: int
    frame_index: Annotated[int, Field(ge=0)]
    ts_ms: Annotated[int, Field(ge=0)]
    """Mốc thời gian của khung hình (đồng hồ khung hình, đơn điệu). Engine chỉ dùng mốc này."""
    image_size: tuple[Annotated[int, Field(gt=0)], Annotated[int, Field(gt=0)]]
    """(width, height) theo pixel."""
    persons: list[PersonPose]
    face: FaceObservation | None = None
    """None: khung này không chạy face (do `face.run_every_n_frames`)."""
    source_ok: bool
