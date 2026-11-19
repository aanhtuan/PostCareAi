"""F30 video slice: authorization, process/session lifecycle and live-data isolation."""

from unittest.mock import Mock

import pytest
from sqlalchemy import select

from postcare.api import video_demo
from postcare.db.models import AuditLog, Camera, MonitoringSession


@pytest.fixture
def demo(app, client, monkeypatch, tmp_path):
    app.state.settings.demo_enabled = True
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"test source; never launched")
    monkeypatch.setattr(video_demo, "VIDEO_PATH", clip)
    monkeypatch.setattr(video_demo, "DEMO_RUNS_DIR", tmp_path)
    proc = Mock()
    proc.poll.return_value = None
    proc.wait.return_value = 0
    spawn = Mock(return_value=proc)
    monkeypatch.setattr(video_demo, "spawn_worker", spawn)
    return proc, spawn


def test_disabled_and_roles(client, app, login, demo):
    app.state.settings.demo_enabled = False
    assert (
        client.post(
            "/api/v1/demo/start", json={"clip_id": "pexels-8090735"}, headers=login("admin")
        ).status_code
        == 404
    )
    app.state.settings.demo_enabled = True
    assert client.post("/api/v1/demo/prepare").status_code == 401
    for role in ("nurse", "doctor"):
        assert client.post("/api/v1/demo/prepare", headers=login(role)).status_code == 403
    assert not demo[1].called


def test_invalid_or_missing_source_does_not_create_session(client, login, demo, db, monkeypatch):
    h = login("admin")
    assert (
        client.post(
            "/api/v1/demo/start", json={"clip_id": "../../private.mp4"}, headers=h
        ).status_code
        == 422
    )
    monkeypatch.setattr(video_demo, "VIDEO_PATH", video_demo.VIDEO_PATH.with_name("missing.mp4"))
    assert (
        client.post("/api/v1/demo/start", json={"clip_id": "pexels-8090735"}, headers=h).status_code
        == 409
    )
    assert not demo[1].called
    assert db.scalar(select(MonitoringSession)) is None


def start(client, login):
    r = client.post(
        "/api/v1/demo/start", json={"clip_id": "pexels-8090735"}, headers=login("admin")
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_runs_isolated_and_old_tab_cannot_stop_new_run(client, login, demo, db, open_session):
    old_camera = db.get(Camera, 1)
    original = (old_camera.source, old_camera.roi_polygon, old_camera.display_mode)
    first = start(client, login)
    assert first["bed_id"] != 1
    assert first["session_id"] != open_session["id"]
    assert (
        client.post(
            "/api/v1/demo/start", json={"clip_id": "pexels-8090735"}, headers=login("admin")
        ).status_code
        == 409
    )
    stopped = client.post(
        "/api/v1/demo/stop", json={"session_id": first["session_id"]}, headers=login("admin")
    )
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "STOPPED"
    second = start(client, login)
    assert second["session_id"] != first["session_id"]
    assert (
        client.post(
            "/api/v1/demo/stop", json={"session_id": first["session_id"]}, headers=login("admin")
        ).status_code
        == 409
    )
    db.expire_all()
    assert db.get(MonitoringSession, first["session_id"]).ended_at is not None
    assert db.get(MonitoringSession, second["session_id"]).ended_at is None
    assert db.get(MonitoringSession, open_session["id"]).ended_at is None
    old_camera = db.get(Camera, 1)
    assert (old_camera.source, old_camera.roi_polygon, old_camera.display_mode) == original


def test_eof_and_failure_close_session_and_audit(client, login, demo, db):
    run = start(client, login)
    demo[0].poll.return_value = 0
    status = client.get("/api/v1/demo", headers=login("nurse")).json()
    assert status["run"]["status"] == "COMPLETED"
    db.expire_all()
    assert db.get(MonitoringSession, run["session_id"]).ended_at is not None
    assert db.scalar(select(AuditLog).where(AuditLog.action == "demo.completed")) is not None
    demo[0].poll.return_value = None
    demo[1].side_effect = OSError("cannot spawn")
    assert (
        client.post(
            "/api/v1/demo/start", json={"clip_id": "pexels-8090735"}, headers=login("admin")
        ).status_code
        == 503
    )
    db.expire_all()
    assert not list(
        db.scalars(select(MonitoringSession).where(MonitoringSession.ended_at.is_(None)))
    )


def test_preparation_preserves_saved_roi_and_mode(client, login, demo, db):
    h = login("admin")
    prepared = client.post("/api/v1/demo/prepare", headers=h).json()
    camera = db.get(Camera, prepared["camera_id"])
    camera.roi_polygon = [[0, 0], [1, 0], [1, 1], [0, 1]]
    db.commit()
    assert client.post("/api/v1/demo/prepare", headers=h).status_code == 200
    db.refresh(camera)
    assert camera.roi_polygon == [[0, 0], [1, 0], [1, 1], [0, 1]]


def test_restart_recovers_audited_session_without_adopting_a_process(client, app, login, demo, db):
    run = start(client, login)
    app.state.video_demo = video_demo.VideoDemo(app.state.settings, app.state.frames)
    status = client.get("/api/v1/demo", headers=login("admin")).json()
    assert status["run"]["status"] == "INTERRUPTED"
    assert (
        client.post(
            "/api/v1/demo/start", json={"clip_id": "pexels-8090735"}, headers=login("admin")
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/demo/stop", json={"session_id": run["session_id"]}, headers=login("admin")
        ).status_code
        == 200
    )
    db.expire_all()
    assert db.get(MonitoringSession, run["session_id"]).ended_at is not None


def test_stuck_worker_timeout_closes_only_demo(client, app, login, demo, db, open_session):
    run = start(client, login)
    app.state.video_demo.started_at -= app.state.settings.demo_max_run_s + 1
    result = client.get("/api/v1/demo", headers=login("admin")).json()
    assert result["run"]["status"] == "FAILED"
    demo[0].wait.assert_called_once()
    db.expire_all()
    assert db.get(MonitoringSession, run["session_id"]).ended_at is not None
    assert db.get(MonitoringSession, open_session["id"]).ended_at is None


def test_shutdown_reaps_worker_and_closes_session(client, app, login, demo, db):
    run = start(client, login)
    app.state.video_demo.shutdown(db, app.state.hub)
    demo[0].wait.assert_called_once()
    assert app.state.video_demo.proc is None
    db.expire_all()
    assert db.get(MonitoringSession, run["session_id"]).ended_at is not None


def test_eof_marker_closes_session_before_slow_process_cleanup(client, app, login, demo, db):
    run = start(client, login)
    marker = video_demo.DEMO_RUNS_DIR / f"session-{run['session_id']}.completed"
    marker.touch()
    state = client.get("/api/v1/demo", headers=login("admin")).json()
    assert state["run"]["status"] == "FINISHING"
    assert app.state.video_demo.proc is not None
    db.expire_all()
    assert db.get(MonitoringSession, run["session_id"]).ended_at is not None
    assert db.get(Camera, run["camera_id"]).status.value == "OFFLINE"
    assert (
        client.post(
            "/api/v1/demo/start", json={"clip_id": "pexels-8090735"}, headers=login("admin")
        ).status_code
        == 409
    )
    demo[0].poll.return_value = 0
    assert client.get("/api/v1/demo", headers=login("admin")).json()["run"]["status"] == "COMPLETED"
