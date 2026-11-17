"""F10 AC2: EngineConfig đọc YAML mặc định, hợp nhất override theo camera, config_hash."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from postcare.schemas.engine_config import EngineConfig, EngineConfigError
from postcare.schemas.observation import KeypointName

ROOT = Path(__file__).resolve().parents[3]
DEFAULT = ROOT / "config" / "engine.default.yaml"


def _raw() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(DEFAULT.read_text(encoding="utf-8"))
    return data


def _write(tmp_path: Path, data: dict[str, Any], name: str = "engine.yaml") -> Path:
    p = tmp_path / name
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def test_load_default_config() -> None:
    cfg = EngineConfig.load(DEFAULT)
    assert cfg.version == 1
    assert cfg.pose.num_poses == 2
    assert cfg.pose.required_keypoints == [
        KeypointName.LEFT_SHOULDER,
        KeypointName.RIGHT_SHOULDER,
        KeypointName.LEFT_HIP,
        KeypointName.RIGHT_HIP,
    ]
    assert cfg.posture.sitting_enter_deg == 55
    assert cfg.min_duration_s.AT_EDGE == 1.5
    assert cfg.min_duration_s.RETURN_TO_BED == 3.0
    assert cfg.debounce.same_code_same_session_s == 60
    assert cfg.face.signals.eyes_closed.keys == ["eyeBlinkLeft", "eyeBlinkRight"]
    assert cfg.face.signals.mouth_change.threshold == 0.5
    assert cfg.rest.active_hold_s == 2.0
    assert cfg.privacy.pixelate_blocks == 12


def test_dump_covers_every_yaml_key() -> None:
    """Không có khóa nào của YAML bị model bỏ sót (dump lại phải đủ cấu trúc)."""
    cfg = EngineConfig.load(DEFAULT)
    assert cfg.model_dump(mode="json") == _raw()


def test_override_deep_merge(tmp_path: Path) -> None:
    override = {
        "posture": {"sitting_enter_deg": 60},
        "face": {"signals": {"brow_down": {"threshold": 0.7}}},
    }
    cfg = EngineConfig.load(DEFAULT, overrides=override)
    assert cfg.posture.sitting_enter_deg == 60
    # Khóa anh em giữ nguyên giá trị mặc định
    assert cfg.posture.sitting_exit_deg == 45
    assert cfg.face.signals.brow_down.threshold == 0.7
    assert cfg.face.signals.brow_down.keys == ["browDownLeft", "browDownRight"]
    # Override từ file config/cameras/<setup>.yaml cho cùng kết quả
    from_file = EngineConfig.load(DEFAULT, overrides=_write(tmp_path, override, "setup.yaml"))
    assert from_file == cfg


def test_override_does_not_mutate_input() -> None:
    override: dict[str, Any] = {"posture": {"sitting_enter_deg": 60}}
    EngineConfig.load(DEFAULT, overrides=override)
    EngineConfig.load(DEFAULT, overrides=override)
    assert override == {"posture": {"sitting_enter_deg": 60}}
    assert EngineConfig.load(DEFAULT).posture.sitting_enter_deg == 55


def test_wrong_type_error_mentions_key() -> None:
    with pytest.raises(EngineConfigError, match=r"posture\.sitting_enter_deg"):
        EngineConfig.load(DEFAULT, overrides={"posture": {"sitting_enter_deg": "abc"}})
    # Chế độ strict: chuỗi số cũng không được ép kiểu ngầm
    with pytest.raises(EngineConfigError, match=r"posture\.sitting_enter_deg"):
        EngineConfig.load(DEFAULT, overrides={"posture": {"sitting_enter_deg": "55"}})
    with pytest.raises(EngineConfigError, match=r"face\.enabled"):
        EngineConfig.load(DEFAULT, overrides={"face": {"enabled": "yes please"}})
    with pytest.raises(EngineConfigError, match=r"pose\.required_keypoints"):
        EngineConfig.load(DEFAULT, overrides={"pose": {"required_keypoints": ["left_toe"]}})


def test_unknown_key_rejected() -> None:
    with pytest.raises(EngineConfigError, match=r"posture\.siting_enter_deg"):
        EngineConfig.load(DEFAULT, overrides={"posture": {"siting_enter_deg": 50}})
    with pytest.raises(EngineConfigError, match=r"min_duration_s\.WALKING"):
        EngineConfig.load(DEFAULT, overrides={"min_duration_s": {"WALKING": 1.0}})
    with pytest.raises(EngineConfigError, match=r"unknown_block"):
        EngineConfig.load(DEFAULT, overrides={"unknown_block": {"a": 1}})


def test_missing_key_rejected(tmp_path: Path) -> None:
    data = _raw()
    del data["posture"]["lying_exit_deg"]
    with pytest.raises(EngineConfigError, match=r"posture\.lying_exit_deg"):
        EngineConfig.load(_write(tmp_path, data))
    data = _raw()
    del data["rest"]
    with pytest.raises(EngineConfigError, match=r"\brest\b"):
        EngineConfig.load(_write(tmp_path, data))


def test_invalid_files_rejected(tmp_path: Path) -> None:
    with pytest.raises(EngineConfigError, match=r"missing\.yaml"):
        EngineConfig.load(tmp_path / "missing.yaml")
    bad = tmp_path / "list.yaml"
    bad.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(EngineConfigError):
        EngineConfig.load(bad)
    with pytest.raises(EngineConfigError):
        EngineConfig.load(DEFAULT, overrides=bad)


def test_config_hash_stable_and_changes_with_override(tmp_path: Path) -> None:
    h = EngineConfig.load(DEFAULT).config_hash()
    assert len(h) == 64
    assert int(h, 16) >= 0
    assert EngineConfig.load(DEFAULT).config_hash() == h
    # Override rỗng hoặc trùng giá trị mặc định → hash không đổi
    assert EngineConfig.load(DEFAULT, overrides={}).config_hash() == h
    same = {"posture": {"sitting_enter_deg": 55}}
    assert EngineConfig.load(DEFAULT, overrides=same).config_hash() == h
    # Thứ tự khóa trong file không ảnh hưởng
    reordered = dict(reversed(list(_raw().items())))
    assert EngineConfig.load(_write(tmp_path, reordered)).config_hash() == h
    # Đổi một ngưỡng → hash đổi
    changed = EngineConfig.load(DEFAULT, overrides={"posture": {"sitting_enter_deg": 60}})
    assert changed.config_hash() != h


def test_config_hash_ignores_privacy() -> None:
    h = EngineConfig.load(DEFAULT).config_hash()
    cfg = EngineConfig.load(DEFAULT, overrides={"privacy": {"pixelate_blocks": 20}})
    assert cfg.privacy.pixelate_blocks == 20
    assert cfg.config_hash() == h
