"""F25 AC1: face adapter + cổng chất lượng với model thật (marker `vision`, `make test-vision`).

Cần `face_landmarker.task` và `pose_landmarker_*.task` trong `models/` (`make models`) và một clip
cận mặt. Mặc định dùng clip stock `data/external/pexels/pexels-6010768.mp4` (người ngồi trên giường
bệnh, mặt rõ; datasets.md). Đổi thư mục bằng `POSTCARE_DATA_DIR`, `POSTCARE_MODELS_DIR`; đổi clip
bằng `POSTCARE_FACE_CLIP`. Thiếu model hoặc video → skip. Không ghi khung hình ra đĩa.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from postcare.vision.inference.face_gate import FaceGate
from postcare.vision.inference.face_landmarker import (
    MediaPipeFaceAdapter,
    blendshape_keys_from_config,
)

from postcare.engine import Engine
from postcare.pipeline import process_frame
from postcare.schemas.context import EngineContext
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.enums import FaceStatus
from postcare.schemas.roi import RoiPolygon
from postcare.settings import REPO_ROOT
from postcare.vision.camera import FileSource
from postcare.vision.inference.pose_mediapipe import MediaPipePoseAdapter
from postcare.vision.models import load_manifest

pytestmark = pytest.mark.vision

DATA_DIR = Path(os.environ.get("POSTCARE_DATA_DIR", REPO_ROOT / "data"))
MODELS_DIR = Path(os.environ.get("POSTCARE_MODELS_DIR", REPO_ROOT / "models"))
DEFAULT_CLIP = DATA_DIR / "external" / "pexels" / "pexels-6010768.mp4"
FULL_FRAME_ROI = RoiPolygon(points=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])


def _clip() -> Path:
    path = Path(os.environ.get("POSTCARE_FACE_CLIP", DEFAULT_CLIP))
    if not path.is_file():
        pytest.skip(f"Không có clip cận mặt {path}")
    return path


def _models() -> tuple[Path, Path]:
    manifest = load_manifest(REPO_ROOT / "config" / "models.yaml")
    assert manifest.face is not None
    pose = MODELS_DIR / manifest.pose_entry().filename
    face = MODELS_DIR / manifest.face.filename
    for path in (pose, face):
        if not path.is_file():
            pytest.skip(f"Thiếu model {path}: chạy `make models`")
    return pose, face


def test_face_adapter_real_model() -> None:
    pose_path, face_path = _models()
    clip = _clip()
    config = EngineConfig.load(REPO_ROOT / "config" / "engine.default.yaml")
    keys = blendshape_keys_from_config(config)
    pose = MediaPipePoseAdapter.from_config(pose_path, config)
    detector = MediaPipeFaceAdapter(face_path, keys)
    gate = FaceGate.from_config(config, detector)
    engine = Engine(config, EngineContext(camera_id=1, roi_polygon=FULL_FRAME_ROI))
    faces = []
    try:
        with FileSource(clip, max_fps=10) as src:
            for _ in range(40):
                frame = src.read()
                if frame is None:
                    break
                obs, _ = process_frame(frame, pose, engine, face=gate)
                faces.append(obs.face)
    finally:
        pose.close()
        detector.close()
    assert faces, "không đọc được khung nào"
    ran = [f for f in faces if f is not None]
    # run_every_n_frames: chỉ một phần khung chạy face.
    assert len(ran) == (len(faces) + config.face.run_every_n_frames - 1) // (
        config.face.run_every_n_frames
    )
    ok = [f for f in ran if f.status == FaceStatus.OK]
    assert ok, f"không có khung OK: {[f.status.value for f in ran]}"
    assert all(set(f.blendshapes) == keys for f in ok)
    assert all(f.head_box_px >= config.face.min_head_box_px for f in ok)
    assert gate.error_count == 0
