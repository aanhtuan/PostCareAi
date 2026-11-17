"""F12 AC1 (vision): `postcare replay --video` với model thật trên clip trong `data/`.

Cần model (`make models`) và clip `data/external/pexels/pexels-8090735.mp4` (datasets.md) kèm
`config/cameras/pexels-8090735.yaml`. Đổi thư mục bằng `POSTCARE_DATA_DIR`, `POSTCARE_MODELS_DIR`.
Thiếu model hoặc video → skip. Kết quả ghi vào `tmp_path`, không ghi khung hình.
"""

import json
import os
from pathlib import Path

import pytest
from postcare.replay.writers import EventRecord, FrameRecord
from typer.testing import CliRunner

from postcare.cli.main import app
from postcare.schemas.observation import FrameObservation
from postcare.settings import REPO_ROOT
from postcare.vision.models import load_manifest

pytestmark = pytest.mark.vision

DATA_DIR = Path(os.environ.get("POSTCARE_DATA_DIR", REPO_ROOT / "data"))
MODELS_DIR = Path(os.environ.get("POSTCARE_MODELS_DIR", REPO_ROOT / "models"))
CLIP = DATA_DIR / "external" / "pexels" / "pexels-8090735.mp4"
CAMERA = REPO_ROOT / "config" / "cameras" / "pexels-8090735.yaml"


def test_replay_real_video(tmp_path: Path) -> None:
    if not CLIP.is_file():
        pytest.skip(f"Không có video {CLIP}")
    model = MODELS_DIR / load_manifest(REPO_ROOT / "config" / "models.yaml").pose_entry().filename
    if not model.is_file():
        pytest.skip(f"Thiếu model {model}: chạy `make models`")
    out = tmp_path / "run"
    result = CliRunner().invoke(
        app,
        [
            "replay",
            "--video",
            str(CLIP),
            "--camera-config",
            str(CAMERA),
            "--out",
            str(out),
            "--models-dir",
            str(MODELS_DIR),
            "--max-fps",
            "5",
            "--preview",
        ],
    )
    assert result.exit_code == 0, result.output
    observations = [
        FrameObservation.model_validate_json(line)
        for line in (out / "observations.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert observations
    assert any(o.persons for o in observations)
    frames = [
        FrameRecord.model_validate_json(line)
        for line in (out / "frames.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(frames) == len(observations)
    for line in (out / "events.jsonl").read_text(encoding="utf-8").splitlines():
        EventRecord.model_validate_json(line)
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert run["mode"] == "video"
    assert run["frames"] == len(observations)
    assert run["model"]["variant"] == "full"
    assert (out / "preview.mp4").stat().st_size > 0

    # Chạy lại chỉ engine từ observations.jsonl cho cùng frames.jsonl (offline = realtime).
    again = tmp_path / "again"
    result = CliRunner().invoke(
        app,
        [
            "replay",
            "--from-observations",
            str(out / "observations.jsonl"),
            "--camera-config",
            str(CAMERA),
            "--out",
            str(again),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (again / "frames.jsonl").read_bytes() == (out / "frames.jsonl").read_bytes()
    assert (again / "events.jsonl").read_bytes() == (out / "events.jsonl").read_bytes()
