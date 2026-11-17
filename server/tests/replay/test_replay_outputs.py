"""F12 AC1: replay xuất observations/events/frames JSONL + run.json (nguồn giả, adapter giả)."""

import json
from pathlib import Path

import pytest
from postcare.replay.camera_config import load_camera_config
from postcare.replay.runner import OUTPUT_FILES, OutputExistsError, replay_video
from postcare.replay.writers import EventRecord, FrameRecord
from typer.testing import CliRunner

from postcare.cli.main import app
from postcare.engine import Engine
from postcare.pipeline import process_frame
from postcare.schemas.observation import FrameObservation
from tests.replay.helpers import (
    DEFAULT_ENGINE,
    fake_source_and_adapter,
    scenario,
    write_camera_yaml,
    write_observations,
)

RUN_KEYS = {
    "mode",
    "video",
    "observations",
    "camera_config",
    "engine_config",
    "config_hash",
    "code_version",
    "model",
    "video_duration_s",
    "frames",
    "dropped_frames",
    "events",
    "fps_processing",
    "cpu_percent",
    "ram_peak_mb",
    "elapsed_s",
    "started_at",
}

cli = CliRunner()


def _run(tmp_path: Path, out: Path, *, overwrite: bool = False) -> None:
    camera = load_camera_config(write_camera_yaml(tmp_path / "cam.yaml"))
    config = camera.engine_config(DEFAULT_ENGINE)
    source, adapter = fake_source_and_adapter(scenario())
    replay_video(source, adapter, camera, config, out, overwrite=overwrite)


def test_replay_writes_all_outputs(tmp_path: Path) -> None:
    out = tmp_path / "runs" / "r1"
    _run(tmp_path, out)
    assert {p.name for p in out.iterdir()} == set(OUTPUT_FILES)
    n = len(scenario())

    obs_lines = (out / "observations.jsonl").read_text(encoding="utf-8").splitlines()
    observations = [FrameObservation.model_validate_json(line) for line in obs_lines]
    assert len(observations) == n
    assert [o.frame_index for o in observations] == list(range(n))

    frame_lines = (out / "frames.jsonl").read_text(encoding="utf-8").splitlines()
    frames = [FrameRecord.model_validate_json(line) for line in frame_lines]
    assert len(frames) == n
    assert [f.ts_ms for f in frames] == [o.ts_ms for o in observations]
    assert {f.persons for f in frames} == {0, 1}
    assert "NO_OBSERVATION" in {f.body_state for f in frames}

    for line in (out / "events.jsonl").read_text(encoding="utf-8").splitlines():
        EventRecord.model_validate_json(line)

    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert set(run) >= RUN_KEYS
    assert run["mode"] == "video"
    assert run["frames"] == n
    camera = load_camera_config(tmp_path / "cam.yaml")
    assert run["config_hash"] == camera.engine_config(DEFAULT_ENGINE).config_hash()


def test_replay_refuses_existing_out_without_overwrite(tmp_path: Path) -> None:
    out = tmp_path / "r1"
    _run(tmp_path, out)
    with pytest.raises(OutputExistsError):
        _run(tmp_path, out)
    _run(tmp_path, out, overwrite=True)
    assert (out / "run.json").is_file()


def test_replay_empty_existing_out_is_ok(tmp_path: Path) -> None:
    out = tmp_path / "r1"
    out.mkdir()
    _run(tmp_path, out)
    assert (out / "frames.jsonl").is_file()


def test_process_frame_is_shared_pipeline(tmp_path: Path) -> None:
    camera = load_camera_config(write_camera_yaml(tmp_path / "cam.yaml"))
    config = camera.engine_config(DEFAULT_ENGINE)
    observations = scenario()[:5]
    source, adapter = fake_source_and_adapter(observations)
    engine = Engine(config, camera.context())
    with source:
        frame = source.read()
    assert frame is not None
    obs, output = process_frame(frame, adapter, engine)
    assert obs.persons == observations[0].persons
    assert obs.camera_id == camera.camera_id
    assert output.state_changed


def _from_obs_args(tmp_path: Path, cam: Path, out: Path) -> list[str]:
    obs = write_observations(tmp_path / "obs.jsonl", scenario())
    return [
        "replay",
        "--from-observations",
        str(obs),
        "--camera-config",
        str(cam),
        "--out",
        str(out),
    ]


def test_cli_out_exists_exits_nonzero(tmp_path: Path) -> None:
    args = _from_obs_args(tmp_path, write_camera_yaml(tmp_path / "cam.yaml"), tmp_path / "out")
    first = cli.invoke(app, args)
    assert first.exit_code == 0, first.output
    second = cli.invoke(app, args)
    assert second.exit_code != 0
    assert "--overwrite" in second.output
    third = cli.invoke(app, [*args, "--overwrite"])
    assert third.exit_code == 0, third.output


def test_cli_bad_roi_exits_nonzero(tmp_path: Path) -> None:
    cam = write_camera_yaml(tmp_path / "cam.yaml", roi_polygon=[[0, 0], [1, 1], [1, 0], [0, 1]])
    result = cli.invoke(app, _from_obs_args(tmp_path, cam, tmp_path / "out"))
    assert result.exit_code != 0
    assert "roi_polygon" in result.output
    assert not (tmp_path / "out" / "events.jsonl").exists()


def test_cli_video_missing_model_exits_nonzero(tmp_path: Path) -> None:
    cam = write_camera_yaml(tmp_path / "cam.yaml")
    video = tmp_path / "clip.avi"
    video.write_bytes(b"")
    result = cli.invoke(
        app,
        [
            "replay",
            "--video",
            str(video),
            "--camera-config",
            str(cam),
            "--out",
            str(tmp_path / "out"),
            "--models-dir",
            str(tmp_path / "no-models"),
        ],
    )
    assert result.exit_code != 0
    assert "make models" in result.output


def test_cli_requires_exactly_one_input(tmp_path: Path) -> None:
    cam = write_camera_yaml(tmp_path / "cam.yaml")
    result = cli.invoke(
        app, ["replay", "--camera-config", str(cam), "--out", str(tmp_path / "out")]
    )
    assert result.exit_code != 0
