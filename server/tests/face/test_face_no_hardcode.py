"""F25 AC3 (R6; event-engine.md mục 8): tên blendshape chỉ nằm trong config, không trong code."""

from __future__ import annotations

import yaml

from postcare.settings import REPO_ROOT

SRC = REPO_ROOT / "server" / "src" / "postcare"

# 52 blendshape của MediaPipe Face Landmarker (model card "Face Blendshapes V2").
MEDIAPIPE_BLENDSHAPES = [
    "_neutral",
    "browDownLeft",
    "browDownRight",
    "browInnerUp",
    "browOuterUpLeft",
    "browOuterUpRight",
    "cheekPuff",
    "cheekSquintLeft",
    "cheekSquintRight",
    "eyeBlinkLeft",
    "eyeBlinkRight",
    "eyeLookDownLeft",
    "eyeLookDownRight",
    "eyeLookInLeft",
    "eyeLookInRight",
    "eyeLookOutLeft",
    "eyeLookOutRight",
    "eyeLookUpLeft",
    "eyeLookUpRight",
    "eyeSquintLeft",
    "eyeSquintRight",
    "eyeWideLeft",
    "eyeWideRight",
    "jawForward",
    "jawLeft",
    "jawOpen",
    "jawRight",
    "mouthClose",
    "mouthDimpleLeft",
    "mouthDimpleRight",
    "mouthFrownLeft",
    "mouthFrownRight",
    "mouthFunnel",
    "mouthLeft",
    "mouthLowerDownLeft",
    "mouthLowerDownRight",
    "mouthPressLeft",
    "mouthPressRight",
    "mouthPucker",
    "mouthRight",
    "mouthRollLower",
    "mouthRollUpper",
    "mouthShrugLower",
    "mouthShrugUpper",
    "mouthSmileLeft",
    "mouthSmileRight",
    "mouthStretchLeft",
    "mouthStretchRight",
    "mouthUpperUpLeft",
    "mouthUpperUpRight",
    "noseSneerLeft",
    "noseSneerRight",
]


def test_config_keys_are_mediapipe_blendshapes() -> None:
    data = yaml.safe_load((REPO_ROOT / "config" / "engine.default.yaml").read_text("utf-8"))
    keys = {k for sig in data["face"]["signals"].values() for k in sig["keys"]}
    assert keys
    assert keys <= set(MEDIAPIPE_BLENDSHAPES), keys - set(MEDIAPIPE_BLENDSHAPES)


def test_no_blendshape_names_hardcoded() -> None:
    found: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        found += [f"{path.relative_to(SRC)}: {n}" for n in MEDIAPIPE_BLENDSHAPES if n in text]
    assert not found, "Tên blendshape viết cứng trong code (phải đọc từ config):\n" + "\n".join(
        found
    )
