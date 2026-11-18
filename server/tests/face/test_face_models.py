"""F25 R1: `face_landmarker.task` nằm trong manifest `make models` (URL cố định + sha256)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from typer.testing import CliRunner

from postcare.cli.main import app
from postcare.settings import REPO_ROOT
from postcare.vision.models import load_manifest


def test_repo_manifest_has_face_model() -> None:
    manifest = load_manifest(REPO_ROOT / "config" / "models.yaml")
    assert manifest.face is not None
    assert manifest.face.filename == "face_landmarker.task"
    assert manifest.face.url.startswith("https://storage.googleapis.com/mediapipe-models/")
    assert "/float16/1/" in manifest.face.url


def test_models_cli_downloads_face_model(tmp_path: Path) -> None:
    remote = tmp_path / "remote"
    remote.mkdir()
    pose = remote / "pose_landmarker_full.task"
    pose.write_bytes(b"pose")
    face = remote / "face_landmarker.task"
    face.write_bytes(b"face-bytes")

    def entry(name: str, path: Path) -> dict[str, str]:
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        return {"name": name, "url": path.as_uri(), "filename": path.name, "sha256": sha}

    manifest = tmp_path / "models.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "pose": {"default": "full", "variants": [entry("full", pose)]},
                "face": entry("face", face),
            }
        ),
        encoding="utf-8",
    )
    dest = tmp_path / "models"
    result = CliRunner().invoke(app, ["models", "--manifest", str(manifest), "--dest", str(dest)])
    assert result.exit_code == 0, result.output
    assert (dest / "face_landmarker.task").read_bytes() == b"face-bytes"
    assert "face_landmarker.task" in result.output
