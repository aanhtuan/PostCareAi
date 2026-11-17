"""F12 AC2: `--from-observations` chạy lại chỉ engine, xác định từng byte, không cần MediaPipe."""

import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from postcare.cli.main import app
from postcare.replay.writers import EventRecord, dump_line
from postcare.schemas.enums import ObservationQuality, Priority
from postcare.schemas.events import EngineEvent, EventCode
from postcare.settings import SERVER_DIR
from tests.replay.helpers import scenario, write_camera_yaml, write_observations

cli = CliRunner()


def _replay(obs: Path, cam: Path, out: Path) -> None:
    args = ["replay", "--from-observations", str(obs), "--camera-config", str(cam)]
    result = cli.invoke(app, [*args, "--out", str(out)])
    assert result.exit_code == 0, result.output


def test_from_observations_deterministic(tmp_path: Path) -> None:
    obs = write_observations(tmp_path / "obs.jsonl", scenario())
    cam = write_camera_yaml(tmp_path / "cam.yaml")
    _replay(obs, cam, tmp_path / "a")
    _replay(obs, cam, tmp_path / "b")
    for name in ("events.jsonl", "frames.jsonl", "observations.jsonl"):
        first = (tmp_path / "a" / name).read_bytes()
        assert first == (tmp_path / "b" / name).read_bytes(), name
        assert b"\r\n" not in first
        first.decode("utf-8")
    frames = (tmp_path / "a" / "frames.jsonl").read_bytes()
    assert frames.count(b"\n") == len(scenario())
    run = json.loads((tmp_path / "a" / "run.json").read_text(encoding="utf-8"))
    assert run["mode"] == "observations"
    assert run["video"] is None


def test_from_observations_output_matches_video_mode_observations(tmp_path: Path) -> None:
    """Chạy lại từ observations.jsonl của một lần chạy cho cùng frames.jsonl."""
    obs = write_observations(tmp_path / "obs.jsonl", scenario())
    cam = write_camera_yaml(tmp_path / "cam.yaml")
    _replay(obs, cam, tmp_path / "a")
    _replay(tmp_path / "a" / "observations.jsonl", cam, tmp_path / "b")
    a = (tmp_path / "a" / "frames.jsonl").read_bytes()
    assert a == (tmp_path / "b" / "frames.jsonl").read_bytes()


def test_event_line_has_fixed_field_order() -> None:
    event = EngineEvent(
        code=EventCode.BED_EXIT,
        priority=Priority.HIGH,
        occurred_at_ms=1000,
        detected_at_ms=2000,
        confidence=0.9,
        observation_quality=ObservationQuality.GOOD,
        explanation={"rule_id": "bed_exit_v1", "hip_out_s": 1.2},
    )
    record = EventRecord(**{**event.model_dump(), "config_hash": "abc"})
    line = dump_line(record)
    assert line == dump_line(EventRecord.model_validate_json(line))
    assert line.endswith("\n") and line.count("\n") == 1
    keys = list(json.loads(line))
    # F15: `config_hash` là trường của EngineEvent nên thứ tự trường = thứ tự của EngineEvent.
    assert keys == list(EngineEvent.model_fields)
    assert json.loads(line)["config_hash"] == "abc"


def test_broken_observation_line_reports_line_number(tmp_path: Path) -> None:
    obs = write_observations(tmp_path / "obs.jsonl", scenario()[:5])
    lines = obs.read_text(encoding="utf-8").splitlines()
    lines[2] = '{"camera_id": 1, "frame_index": "x"}'
    obs.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cam = write_camera_yaml(tmp_path / "cam.yaml")
    args = ["replay", "--from-observations", str(obs), "--camera-config", str(cam)]
    result = cli.invoke(app, [*args, "--out", str(tmp_path / "out")])
    assert result.exit_code != 0
    assert "dòng 3" in result.output


_NO_MEDIAPIPE_SCRIPT = """
import json, sys
from postcare.cli.main import app
try:
    app(sys.argv[1:], standalone_mode=False)
except SystemExit as exc:
    if exc.code:
        raise
print(json.dumps({"mediapipe": any(m.split(".")[0] == "mediapipe" for m in sys.modules)}))
"""


def test_from_observations_does_not_import_mediapipe(tmp_path: Path) -> None:
    obs = write_observations(tmp_path / "obs.jsonl", scenario()[:20])
    cam = write_camera_yaml(tmp_path / "cam.yaml")
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            _NO_MEDIAPIPE_SCRIPT,
            "replay",
            "--from-observations",
            str(obs),
            "--camera-config",
            str(cam),
            "--out",
            str(tmp_path / "out"),
        ],
        cwd=SERVER_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == {"mediapipe": False}
    assert (tmp_path / "out" / "frames.jsonl").is_file()


def test_from_observations_copies_video_and_model_from_source_run(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    obs = write_observations(src / "observations.jsonl", scenario()[:10])
    source_run = {
        "video": "data/videos/S06.mp4",
        "model": {"variant": "full", "file": "pose_landmarker_full.task"},
        "video_duration_s": 42.0,
    }
    (src / "run.json").write_text(json.dumps(source_run), encoding="utf-8")
    cam = write_camera_yaml(tmp_path / "cam.yaml")
    _replay(obs, cam, tmp_path / "out")
    run = json.loads((tmp_path / "out" / "run.json").read_text(encoding="utf-8"))
    assert run["mode"] == "observations"
    assert run["video"] == source_run["video"]
    assert run["model"] == source_run["model"]
    assert run["video_duration_s"] == 42.0
    assert run["observations"] == str(obs)
