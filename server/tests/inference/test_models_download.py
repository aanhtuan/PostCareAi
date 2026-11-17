"""F11 AC1 (R1, R2): `postcare models` tải model theo manifest và kiểm tra sha256.

Không cần mạng: "server" là file trong `tmp_path`, URL dạng `file://`.
"""

import hashlib
import re
from pathlib import Path

import pytest
import yaml
from postcare.vision.models import (
    ChecksumMismatchError,
    ManifestError,
    ensure_model,
    load_manifest,
)
from typer.testing import CliRunner

from postcare.cli.main import app
from postcare.settings import REPO_ROOT

runner = CliRunner()
CONTENT = {"lite": b"lite-model-bytes", "full": b"full-model-bytes-xx"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest(tmp_path: Path, *, wrong_sha: bool = False) -> Path:
    remote = tmp_path / "remote" / "1"
    remote.mkdir(parents=True)
    variants = []
    for name, data in CONTENT.items():
        src = remote / f"pose_landmarker_{name}.task"
        src.write_bytes(data)
        variants.append(
            {
                "name": name,
                "url": src.as_uri(),
                "filename": src.name,
                "sha256": "0" * 64 if wrong_sha else _sha(data),
            }
        )
    path = tmp_path / "models.yaml"
    path.write_text(
        yaml.safe_dump({"version": 1, "pose": {"default": "full", "variants": variants}}),
        encoding="utf-8",
    )
    return path


def test_models_downloads_missing_file(tmp_path: Path) -> None:
    manifest = load_manifest(_manifest(tmp_path))
    dest = tmp_path / "models"
    result = ensure_model(manifest.pose_entry("lite"), dest)
    assert result.downloaded is True
    assert result.path == dest / "pose_landmarker_lite.task"
    assert result.path.read_bytes() == CONTENT["lite"]
    assert sorted(p.name for p in dest.iterdir()) == [
        "pose_landmarker_lite.task"
    ]  # không sót file tạm


def test_models_skip_when_checksum_ok(tmp_path: Path) -> None:
    manifest = load_manifest(_manifest(tmp_path))
    dest = tmp_path / "models"
    ensure_model(manifest.pose_entry("full"), dest)
    # Xóa nguồn: nếu còn tải lại thì sẽ lỗi.
    (tmp_path / "remote" / "1" / "pose_landmarker_full.task").unlink()
    again = ensure_model(manifest.pose_entry("full"), dest)
    assert again.downloaded is False
    assert again.path.read_bytes() == CONTENT["full"]


def test_models_redownloads_when_existing_file_is_corrupt(tmp_path: Path) -> None:
    manifest = load_manifest(_manifest(tmp_path))
    dest = tmp_path / "models"
    dest.mkdir()
    (dest / "pose_landmarker_lite.task").write_bytes(b"hong")
    result = ensure_model(manifest.pose_entry("lite"), dest)
    assert result.downloaded is True
    assert result.path.read_bytes() == CONTENT["lite"]


def test_models_checksum_mismatch_fails(tmp_path: Path) -> None:
    manifest = load_manifest(_manifest(tmp_path, wrong_sha=True))
    dest = tmp_path / "models"
    with pytest.raises(ChecksumMismatchError, match="sha256"):
        ensure_model(manifest.pose_entry("lite"), dest)
    assert not dest.exists() or list(dest.iterdir()) == []  # đã xóa file tải dở


def test_models_cli_checksum_mismatch_exits_nonzero(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, wrong_sha=True)
    dest = tmp_path / "models"
    result = runner.invoke(app, ["models", "--manifest", str(manifest), "--dest", str(dest)])
    assert result.exit_code != 0
    assert "sha256" in result.output
    assert not dest.exists() or list(dest.iterdir()) == []


def test_models_cli_downloads_all_then_skips(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    dest = tmp_path / "models"
    args = ["models", "--manifest", str(manifest), "--dest", str(dest)]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    assert sorted(p.name for p in dest.iterdir()) == [
        "pose_landmarker_full.task",
        "pose_landmarker_lite.task",
    ]
    second = runner.invoke(app, args)
    assert second.exit_code == 0, second.output
    assert second.output.count("bỏ qua") == 2


def test_models_cli_single_variant(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    dest = tmp_path / "models"
    result = runner.invoke(
        app, ["models", "--manifest", str(manifest), "--dest", str(dest), "--variant", "lite"]
    )
    assert result.exit_code == 0, result.output
    assert [p.name for p in dest.iterdir()] == ["pose_landmarker_lite.task"]


def test_models_cli_unreachable_url_exits_nonzero(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    (tmp_path / "remote" / "1" / "pose_landmarker_lite.task").unlink()
    result = runner.invoke(
        app,
        ["models", "--manifest", str(manifest), "--dest", str(tmp_path / "m"), "--variant", "lite"],
    )
    assert result.exit_code != 0
    assert "Không tải được" in result.output


def test_unknown_variant_is_clear_error(tmp_path: Path) -> None:
    manifest = load_manifest(_manifest(tmp_path))
    with pytest.raises(ManifestError, match="heavy"):
        manifest.pose_entry("heavy")


def test_manifest_default_must_be_listed(tmp_path: Path) -> None:
    path = _manifest(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["pose"]["default"] = "heavy"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ManifestError, match="default"):
        load_manifest(path)


def test_manifest_rejects_latest_url(tmp_path: Path) -> None:
    path = _manifest(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["pose"]["variants"][0]["url"] = "https://example.com/pose/float16/latest/x.task"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ManifestError, match="latest"):
        load_manifest(path)


def test_repo_manifest_is_pinned_and_complete() -> None:
    """`config/models.yaml` thật: lite/full/heavy (QA#35), URL chính thức có số phiên bản."""
    manifest = load_manifest(REPO_ROOT / "config" / "models.yaml")
    names = [v.name for v in manifest.pose.variants]
    assert names == ["lite", "full", "heavy"]
    assert manifest.pose.default in names
    for v in manifest.pose.variants:
        assert v.url.startswith("https://storage.googleapis.com/mediapipe-models/pose_landmarker/")
        assert re.search(r"/float16/\d+/", v.url), v.url
        assert v.filename == f"pose_landmarker_{v.name}.task"
        assert v.url.endswith("/" + v.filename)
        assert re.fullmatch(r"[0-9a-f]{64}", v.sha256)
