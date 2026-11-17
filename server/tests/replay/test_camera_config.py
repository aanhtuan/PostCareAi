"""F12 R3: định dạng `config/cameras/<setup>.yaml` (ROI chuẩn hóa + override ngưỡng)."""

from pathlib import Path

import pytest

from postcare.replay.camera_config import CameraConfigError, load_camera_config
from postcare.schemas.engine_config import EngineConfig
from postcare.settings import REPO_ROOT
from tests.replay.helpers import DEFAULT_ENGINE, write_camera_yaml

REPO_CAMERAS = sorted((REPO_ROOT / "config" / "cameras").glob("*.yaml"))


def test_load_valid_camera_config(tmp_path: Path) -> None:
    path = write_camera_yaml(tmp_path / "c.yaml", thresholds={"smoothing": {"ema_alpha": 0.6}})
    cam = load_camera_config(path)
    assert cam.camera_id == 1
    assert len(cam.roi_polygon.points) == 4
    assert cam.engine_config(DEFAULT_ENGINE).smoothing.ema_alpha == 0.6
    assert cam.context().roi_polygon == cam.roi_polygon


def test_thresholds_empty_means_default(tmp_path: Path) -> None:
    cam = load_camera_config(write_camera_yaml(tmp_path / "c.yaml", thresholds=None))
    default_hash = EngineConfig.load(DEFAULT_ENGINE).config_hash()
    assert cam.engine_config(DEFAULT_ENGINE).config_hash() == default_hash


@pytest.mark.parametrize(
    ("override", "needle"),
    [
        ({"roi_polygon": [[0.1, 0.1], [0.9, 0.1]]}, "roi_polygon"),
        ({"roi_polygon": [[0.1, 0.1], [1.2, 0.1], [0.5, 0.9]]}, "roi_polygon"),
        ({"roi_polygon": [[0, 0], [1, 1], [1, 0], [0, 1]]}, "roi_polygon"),
        ({"roi_polygon": [[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]]}, "roi_polygon"),
        ({"version": 2}, "version"),
        ({"unknown_key": 1}, "unknown_key"),
        ({"thresholds": {"smoothing": {"ema_alpha": "x"}}}, "smoothing.ema_alpha"),
        ({"thresholds": {"no_such_block": {}}}, "no_such_block"),
    ],
)
def test_invalid_camera_config(tmp_path: Path, override: dict[str, object], needle: str) -> None:
    path = write_camera_yaml(tmp_path / "c.yaml", **override)
    with pytest.raises(CameraConfigError) as err:
        load_camera_config(path).engine_config(DEFAULT_ENGINE)
    assert needle in str(err.value)


def test_missing_or_broken_file(tmp_path: Path) -> None:
    with pytest.raises(CameraConfigError):
        load_camera_config(tmp_path / "missing.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("roi_polygon: [\n", encoding="utf-8")
    with pytest.raises(CameraConfigError):
        load_camera_config(bad)


def test_repo_has_camera_configs() -> None:
    assert len(REPO_CAMERAS) >= 2


@pytest.mark.parametrize("path", REPO_CAMERAS, ids=lambda p: p.name)
def test_repo_camera_configs_are_valid(path: Path) -> None:
    load_camera_config(path).engine_config(DEFAULT_ENGINE)
