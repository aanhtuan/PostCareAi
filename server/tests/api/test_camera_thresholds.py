"""F08 AC3, R4, R6: `GET/PUT /cameras/{id}/thresholds` (override theo camera, EngineConfig)."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from postcare.db.models import AuditLog, Camera
from postcare.schemas.engine_config import EngineConfig
from postcare.settings import REPO_ROOT

Login = Callable[[str], dict[str, str]]
URL = "/api/v1/cameras/1/thresholds"
DEFAULTS = EngineConfig.load(REPO_ROOT / "config" / "engine.default.yaml").model_dump(mode="json")


def _camera(db: Session) -> Camera:
    db.expire_all()
    camera = db.get(Camera, 1)
    assert camera is not None
    return camera


def _audits(db: Session) -> list[AuditLog]:
    db.expire_all()
    q = select(AuditLog).where(AuditLog.action == "camera.update_thresholds")
    return list(db.scalars(q.order_by(AuditLog.id)))


def test_get_thresholds_defaults_overrides_effective(client: TestClient, login: Login) -> None:
    r = client.get(URL, headers=login("admin"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["defaults"] == DEFAULTS
    assert body["overrides"] == {}
    assert body["effective"] == DEFAULTS
    assert isinstance(body["config_version"], int)


def test_put_thresholds_override(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    version = _camera(db).config_version
    overrides = {"posture": {"lying_enter_deg": 20}, "min_duration_s": {"SITTING": 3.0}}
    r = client.put(URL, json={"thresholds": overrides}, headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["overrides"] == overrides
    assert body["effective"]["posture"]["lying_enter_deg"] == 20
    assert body["effective"]["posture"]["lying_exit_deg"] == DEFAULTS["posture"]["lying_exit_deg"]
    assert body["effective"]["min_duration_s"]["SITTING"] == 3.0
    assert body["defaults"] == DEFAULTS
    assert body["config_version"] == version + 1
    camera = _camera(db)
    assert camera.thresholds == overrides and camera.config_version == version + 1
    # GET trả cùng nội dung.
    assert client.get(URL, headers=admin).json() == body


def test_put_thresholds_replaces_all_overrides(client: TestClient, login: Login) -> None:
    admin = login("admin")
    client.put(URL, json={"thresholds": {"posture": {"lying_enter_deg": 20}}}, headers=admin)
    r = client.put(URL, json={"thresholds": {"activity": {"low_threshold": 0.03}}}, headers=admin)
    body = r.json()
    assert body["overrides"] == {"activity": {"low_threshold": 0.03}}
    assert body["effective"]["posture"]["lying_enter_deg"] == DEFAULTS["posture"]["lying_enter_deg"]


def test_reset_thresholds_with_empty_object(client: TestClient, login: Login, db: Session) -> None:
    admin = login("admin")
    client.put(URL, json={"thresholds": {"posture": {"lying_enter_deg": 20}}}, headers=admin)
    version = _camera(db).config_version
    r = client.put(URL, json={"thresholds": {}}, headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body["overrides"] == {} and body["effective"] == DEFAULTS
    assert body["config_version"] == version + 1
    assert _camera(db).thresholds == {}


@pytest.mark.parametrize(
    ("overrides", "path"),
    [
        ({"posture": {"lying_entr_deg": 20}}, "thresholds.posture.lying_entr_deg"),
        ({"postur": {"lying_enter_deg": 20}}, "thresholds.postur"),
        ({"min_duration_s": {"SLEEPING": 1.0}}, "thresholds.min_duration_s.SLEEPING"),
    ],
)
def test_thresholds_unknown_key_400(
    client: TestClient, login: Login, db: Session, overrides: dict[str, Any], path: str
) -> None:
    _assert_rejected(client, login, db, overrides, path)


@pytest.mark.parametrize(
    ("overrides", "path"),
    [
        ({"posture": {"lying_enter_deg": "20"}}, "thresholds.posture.lying_enter_deg"),
        ({"posture": {"lying_enter_deg": True}}, "thresholds.posture.lying_enter_deg"),
        ({"posture": 5}, "thresholds.posture"),
        ({"face": {"enabled": "yes"}}, "thresholds.face.enabled"),
        ({"pose": {"num_poses": 1.5}}, "thresholds.pose.num_poses"),
    ],
)
def test_thresholds_wrong_type_400(
    client: TestClient, login: Login, db: Session, overrides: dict[str, Any], path: str
) -> None:
    _assert_rejected(client, login, db, overrides, path)


@pytest.mark.parametrize(
    ("overrides", "path"),
    [
        ({"min_duration_s": {"SITTING": -1}}, "thresholds.min_duration_s.SITTING"),
        ({"location": {"edge_distance_torso": -0.1}}, "thresholds.location.edge_distance_torso"),
        ({"pose": {"min_keypoint_visibility": 1.5}}, "thresholds.pose.min_keypoint_visibility"),
    ],
)
def test_thresholds_out_of_range_400(
    client: TestClient, login: Login, db: Session, overrides: dict[str, Any], path: str
) -> None:
    _assert_rejected(client, login, db, overrides, path)


def _assert_rejected(
    client: TestClient, login: Login, db: Session, overrides: dict[str, Any], path: str
) -> None:
    before = _camera(db)
    version, stored = before.config_version, before.thresholds
    r = client.put(URL, json={"thresholds": overrides}, headers=login("admin"))
    assert r.status_code == 400, r.text
    err = r.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    paths = [e["path"] for e in err["details"]["errors"]]
    assert path in paths, paths
    camera = _camera(db)
    assert camera.config_version == version and camera.thresholds == stored
    assert _audits(db) == []


@pytest.mark.parametrize("username", ["nurse", "charge", "doctor"])
def test_thresholds_require_admin(
    client: TestClient, login: Login, db: Session, username: str
) -> None:
    headers = login(username)
    version = _camera(db).config_version
    assert client.get(URL, headers=headers).status_code == 403
    r = client.put(URL, json={"thresholds": {"posture": {"lying_enter_deg": 20}}}, headers=headers)
    assert r.status_code == 403
    assert _camera(db).config_version == version


def test_thresholds_unknown_camera_404(client: TestClient, login: Login) -> None:
    admin = login("admin")
    assert client.get("/api/v1/cameras/9999/thresholds", headers=admin).status_code == 404
    r = client.put("/api/v1/cameras/9999/thresholds", json={"thresholds": {}}, headers=admin)
    assert r.status_code == 404


def test_camera_config_changes_bump_version_and_audit(
    client: TestClient, login: Login, db: Session
) -> None:
    admin = login("admin")
    v0 = _camera(db).config_version
    roi = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.9], [0.2, 0.9]]
    assert client.put("/api/v1/cameras/1/roi", json={"roi_polygon": roi}, headers=admin).is_success
    assert _camera(db).config_version == v0 + 1
    overrides = {"activity": {"high_threshold": 0.2}}
    assert client.put(URL, json={"thresholds": overrides}, headers=admin).is_success
    assert _camera(db).config_version == v0 + 2
    # Không đổi gì: không tăng version, không audit.
    assert client.put(URL, json={"thresholds": overrides}, headers=admin).is_success
    assert _camera(db).config_version == v0 + 2
    # Lưu lỗi: không tăng version.
    bad = {"activity": {"high_threshold": "cao"}}
    assert client.put(URL, json={"thresholds": bad}, headers=admin).status_code == 400
    assert _camera(db).config_version == v0 + 2

    logs = _audits(db)
    assert len(logs) == 1
    assert logs[0].before == {"thresholds": {}, "config_version": v0 + 1}
    assert logs[0].after == {"thresholds": overrides, "config_version": v0 + 2}
    # Worker nhận cấu hình mới qua API nội bộ (F06).
    r = client.get("/internal/v1/cameras/1/config", headers={"X-Worker-Token": _worker_token()})
    assert r.json()["thresholds"] == overrides and r.json()["roi_polygon"] == roi
    assert r.json()["config_version"] == v0 + 2


def _worker_token() -> str:
    from tests.conftest import WORKER_TOKEN

    return WORKER_TOKEN


# ---------- An toàn (review F08): danh sách khóa được phép, sàn/trần, quan hệ ----------


@pytest.mark.parametrize(
    ("overrides", "path"),
    [
        ({"min_duration_s": {"OUT_OF_BED": 0}}, "thresholds.min_duration_s.OUT_OF_BED"),
        ({"min_duration_s": {"STANDING": 0.1}}, "thresholds.min_duration_s.STANDING"),
        ({"min_duration_s": {"AT_EDGE": 3600}}, "thresholds.min_duration_s.AT_EDGE"),
        ({"pose": {"min_keypoint_visibility": 0.0}}, "thresholds.pose.min_keypoint_visibility"),
        (
            {"quality": {"low_quality_to_no_observation_s": 0}},
            "thresholds.quality.low_quality_to_no_observation_s",
        ),
        (
            {"quality": {"observation_lost_event_s": 0}},
            "thresholds.quality.observation_lost_event_s",
        ),
        ({"location": {"edge_distance_torso": 0}}, "thresholds.location.edge_distance_torso"),
        (
            {"abnormal_movement": {"min_conditions": 1}},
            "thresholds.abnormal_movement.min_conditions",
        ),
        (
            {"abnormal_movement": {"min_conditions": 6}},
            "thresholds.abnormal_movement.min_conditions",
        ),
    ],
)
def test_thresholds_safety_limits_400(
    client: TestClient, login: Login, db: Session, overrides: dict[str, Any], path: str
) -> None:
    _assert_rejected(client, login, db, overrides, path)


@pytest.mark.parametrize(
    ("overrides", "path"),
    [
        ({"privacy": {"pixelate_blocks": 2}}, "thresholds.privacy.pixelate_blocks"),
        ({"face": {"enabled": False}}, "thresholds.face.enabled"),
        ({"pose": {"required_keypoints": ["left_hip"]}}, "thresholds.pose.required_keypoints"),
        ({"pose": {"num_poses": 1}}, "thresholds.pose.num_poses"),
        (
            {"debounce": {"same_code_same_session_s": 0}},
            "thresholds.debounce.same_code_same_session_s",
        ),
        (
            {"abnormal_movement": {"hip_drop_speed_torso_per_s": 99}},
            "thresholds.abnormal_movement.hip_drop_speed_torso_per_s",
        ),
        (
            {"abnormal_movement": {"final_low_position_ratio": 1.0}},
            "thresholds.abnormal_movement.final_low_position_ratio",
        ),
        ({"version": 1}, "thresholds.version"),
    ],
)
def test_thresholds_key_not_overridable_400(
    client: TestClient, login: Login, db: Session, overrides: dict[str, Any], path: str
) -> None:
    _assert_rejected(client, login, db, overrides, path)


@pytest.mark.parametrize(
    ("overrides", "path"),
    [
        ({"posture": {"lying_enter_deg": 40}}, "thresholds.posture.lying_exit_deg"),
        ({"posture": {"lying_exit_deg": 45}}, "thresholds.posture.sitting_exit_deg"),
        ({"posture": {"sitting_exit_deg": 60}}, "thresholds.posture.sitting_enter_deg"),
        ({"activity": {"low_threshold": 0.15}}, "thresholds.activity.high_threshold"),
        ({"activity": {"high_threshold": 0.01}}, "thresholds.activity.high_threshold"),
    ],
)
def test_thresholds_relations_400(
    client: TestClient, login: Login, db: Session, overrides: dict[str, Any], path: str
) -> None:
    _assert_rejected(client, login, db, overrides, path)


def test_thresholds_at_floor_accepted(client: TestClient, login: Login) -> None:
    overrides = {
        "min_duration_s": {"OUT_OF_BED": 0.3},
        "pose": {"min_keypoint_visibility": 0.3},
        "abnormal_movement": {"min_conditions": 2},
        "posture": {"lying_enter_deg": 35, "lying_exit_deg": 35},
    }
    r = client.put(URL, json={"thresholds": overrides}, headers=login("admin"))
    assert r.status_code == 200, r.text


def test_get_thresholds_returns_rules_for_web(client: TestClient, login: Login) -> None:
    rules = client.get(URL, headers=login("admin")).json()["rules"]
    assert "min_duration_s.*" in rules["allowed"]
    assert "privacy.*" not in rules["allowed"]
    assert rules["limits"]["min_duration_s.*"]["min"] == 0.3
    relation = {"low": "activity.low_threshold", "high": "activity.high_threshold", "strict": True}
    assert relation in rules["relations"]
