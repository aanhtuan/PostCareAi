"""F08 (review): `config/camera_overrides.yaml` hợp lệ và ngưỡng mặc định thỏa mọi giới hạn."""

from postcare.domain.camera_config import (
    DEFAULT_ENGINE_CONFIG,
    DEFAULT_OVERRIDE_RULES,
    load_override_rules,
    rule_violations,
)
from postcare.schemas.engine_config import EngineConfig


def test_default_config_satisfies_override_rules() -> None:
    rules = load_override_rules(DEFAULT_OVERRIDE_RULES)
    effective = EngineConfig.load(DEFAULT_ENGINE_CONFIG).model_dump(mode="json")
    assert rule_violations(effective, rules) == []


def test_every_limit_and_relation_key_is_overridable() -> None:
    rules = load_override_rules(DEFAULT_OVERRIDE_RULES)
    for key in rules.limits:
        assert rules.is_allowed(key.replace("*", "RAISING")), key
    for rel in rules.relations:
        assert rules.is_allowed(rel.low) and rules.is_allowed(rel.high)
