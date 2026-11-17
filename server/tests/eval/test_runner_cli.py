"""F16 R3, R7, AC4: runner gọi replay F12 cho từng video và lệnh `postcare eval` (không media)."""

import json
from pathlib import Path

from postcare.eval.manifest import validate_files
from postcare.eval.runner import VideoFailure, VideoRun, run_split
from typer.testing import CliRunner

from postcare.cli.main import app
from postcare.settings import REPO_ROOT
from tests.eval.helpers import manifest_row, truth_row, write_dataset
from tests.replay.helpers import (
    fake_source_and_adapter,
    scenario,
    write_camera_yaml,
    write_observations,
)

cli = CliRunner()
ENGINE = REPO_ROOT / "config" / "engine.default.yaml"


def _dataset(tmp_path: Path, *video_ids: str) -> tuple[Path, Path]:
    rows = [manifest_row(v, duration_s="20", path=f"data/videos/{v}.mp4") for v in video_ids]
    return write_dataset(tmp_path, rows, [truth_row(video_ids[0], "SIT_UP", "3.0", "4.0")])


def _obs_dir(tmp_path: Path, *video_ids: str) -> Path:
    root = tmp_path / "cached"
    for v in video_ids:
        (root / v).mkdir(parents=True)
        write_observations(root / v / "observations.jsonl", scenario())
    return root


def test_runner_video_mode_uses_replay(tmp_path: Path) -> None:
    m, t = _dataset(tmp_path, "S03_P01_r1")
    rows = validate_files(m, t).manifest
    video = tmp_path / "data" / "videos" / "S03_P01_r1.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"")  # chỉ cần tồn tại; nguồn khung là FakeFrameSource
    source, adapter = fake_source_and_adapter(scenario())
    results = run_split(
        rows,
        runs_dir=tmp_path / "runs",
        engine_config=ENGINE,
        default_camera_config=write_camera_yaml(tmp_path / "cam.yaml"),
        cameras_dir=tmp_path / "no-cameras",
        data_dir=tmp_path / "data",
        adapter_factory=lambda config: adapter,
        source_factory=lambda path, max_fps: source,
    )
    [res] = results
    assert isinstance(res, VideoRun)
    assert len(res.frames) == len(scenario())
    assert (tmp_path / "runs" / "S03_P01_r1" / "events.jsonl").is_file()
    assert res.run["mode"] == "video"
    assert adapter.closed


def test_runner_missing_video_is_failure_not_crash(tmp_path: Path) -> None:
    m, t = _dataset(tmp_path, "S03_P01_r1")
    rows = validate_files(m, t).manifest
    [res] = run_split(
        rows,
        runs_dir=tmp_path / "runs",
        engine_config=ENGINE,
        default_camera_config=write_camera_yaml(tmp_path / "cam.yaml"),
        cameras_dir=tmp_path,
        data_dir=tmp_path / "data",
        adapter_factory=lambda config: None,  # type: ignore[arg-type,return-value]
    )
    assert isinstance(res, VideoFailure)
    assert "S03_P01_r1" in res.video_id


def test_runner_from_observations_and_reuse(tmp_path: Path) -> None:
    m, t = _dataset(tmp_path, "S03_P01_r1")
    rows = validate_files(m, t).manifest
    kwargs = {
        "runs_dir": tmp_path / "runs",
        "engine_config": ENGINE,
        "default_camera_config": write_camera_yaml(tmp_path / "cam.yaml"),
        "cameras_dir": tmp_path,
        "data_dir": tmp_path / "data",
        "from_observations": _obs_dir(tmp_path, "S03_P01_r1"),
    }
    [first] = run_split(rows, **kwargs)  # type: ignore[arg-type]
    assert isinstance(first, VideoRun)
    assert first.run["mode"] == "observations"
    assert not first.reused
    [second] = run_split(rows, reuse=True, **kwargs)  # type: ignore[arg-type]
    assert isinstance(second, VideoRun)
    assert second.reused
    assert second.frames == first.frames


def test_camera_config_named_after_video_file(tmp_path: Path) -> None:
    m, t = _dataset(tmp_path, "S03_P01_r1")
    rows = validate_files(m, t).manifest
    cams = tmp_path / "cameras"
    cams.mkdir()
    write_camera_yaml(cams / "S03_P01_r1.yaml", camera_id=7)
    [res] = run_split(
        rows,
        runs_dir=tmp_path / "runs",
        engine_config=ENGINE,
        default_camera_config=write_camera_yaml(tmp_path / "cam.yaml"),
        cameras_dir=cams,
        data_dir=tmp_path / "data",
        from_observations=_obs_dir(tmp_path, "S03_P01_r1"),
    )
    assert isinstance(res, VideoRun)
    assert Path(res.run["camera_config"]).name == "S03_P01_r1.yaml"


def test_split_test_rejected(tmp_path: Path) -> None:
    m, t = _dataset(tmp_path, "S03_P01_r1")
    result = cli.invoke(app, ["eval", "--split", "test", "--manifest", str(m), "--truth", str(t)])
    assert result.exit_code != 0
    assert "F29" in result.output
    assert "--frozen" in result.output


def test_check_command_errors_exit_nonzero(tmp_path: Path) -> None:
    m, t = write_dataset(tmp_path, [manifest_row()], [truth_row(event_code="FALL_DOWN")])
    result = cli.invoke(app, ["eval", "check", "--manifest", str(m), "--truth", str(t)])
    assert result.exit_code == 1
    assert "FALL_DOWN" in result.output


def test_check_warns_only(tmp_path: Path) -> None:
    m, t = write_dataset(
        tmp_path,
        [manifest_row("S06_P01_r1"), manifest_row("S06_P01_r2", split="test")],
        [],
    )
    result = cli.invoke(app, ["eval", "check", "--manifest", str(m), "--truth", str(t)])
    assert result.exit_code == 0, result.output
    assert "Cảnh báo" in result.output


def test_eval_invalid_manifest_stops_before_running(tmp_path: Path) -> None:
    m, t = write_dataset(tmp_path, [manifest_row(split="train")], [])
    result = cli.invoke(app, ["eval", "--manifest", str(m), "--truth", str(t)])
    assert result.exit_code == 1
    assert "split" in result.output


def test_eval_from_observations_writes_report(tmp_path: Path) -> None:
    m, t = _dataset(tmp_path, "S03_P01_r1", "S03_P01_r2")
    report = tmp_path / "reports" / "eval-dev.local.md"
    args = [
        "eval",
        "--split", "dev",
        "--manifest", str(m),
        "--truth", str(t),
        "--camera-config", str(write_camera_yaml(tmp_path / "cam.yaml")),
        "--from-observations", str(_obs_dir(tmp_path, "S03_P01_r1", "S03_P01_r2")),
        "--runs-dir", str(tmp_path / "runs"),
        "--report", str(report),
        "--tol-before-s", "2",
        "--tol-after-s", "4",
    ]  # fmt: skip
    result = cli.invoke(app, args)
    assert result.exit_code == 0, result.output
    md = report.read_text(encoding="utf-8")
    assert "[start − 2 s, end + 4 s]" in md
    assert "Số video: 2" in md
    data = json.loads(report.with_suffix(".json").read_text(encoding="utf-8"))
    assert data["split"] == "dev"
    assert len(data["videos"]) == 2
    assert (tmp_path / "runs" / "S03_P01_r2" / "frames.jsonl").is_file()


def test_eval_video_id_filter(tmp_path: Path) -> None:
    m, t = _dataset(tmp_path, "S03_P01_r1", "S03_P01_r2")
    report = tmp_path / "r.local.md"
    result = cli.invoke(
        app,
        [
            "eval",
            "--manifest", str(m),
            "--truth", str(t),
            "--camera-config", str(write_camera_yaml(tmp_path / "cam.yaml")),
            "--from-observations", str(_obs_dir(tmp_path, "S03_P01_r1", "S03_P01_r2")),
            "--runs-dir", str(tmp_path / "runs"),
            "--report", str(report),
            "--video-id", "S03_P01_r2",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "Số video: 1" in report.read_text(encoding="utf-8")
