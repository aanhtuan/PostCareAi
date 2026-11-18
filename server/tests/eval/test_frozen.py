"""F29 R1, R2, AC1: chốt `config_hash` và chặn chạy tập test khi cấu hình lệch (không media)."""

import json
from pathlib import Path

import yaml
from postcare.eval.frozen import read_frozen_hash, run_dir_hashes
from typer.testing import CliRunner

from postcare.cli.main import app
from postcare.replay.camera_config import load_camera_config
from postcare.settings import REPO_ROOT
from tests.eval.helpers import manifest_row, truth_row, write_dataset
from tests.replay.helpers import scenario, write_camera_yaml, write_observations

cli = CliRunner()
ENGINE = REPO_ROOT / "config" / "engine.default.yaml"
VIDEO = "S03_P09_r1"


def _setup(tmp_path: Path) -> dict[str, Path]:
    m, t = write_dataset(
        tmp_path,
        [manifest_row(VIDEO, split="test", participant_id="P09", duration_s="20")],
        [truth_row(VIDEO, "SIT_UP", "3.0", "4.0")],
    )
    cam = write_camera_yaml(tmp_path / "cam.yaml")
    obs = tmp_path / "cached"
    (obs / VIDEO).mkdir(parents=True)
    write_observations(obs / VIDEO / "observations.jsonl", scenario())
    return {"m": m, "t": t, "cam": cam, "obs": obs}


def _hash(cam: Path, engine: Path = ENGINE) -> str:
    return load_camera_config(cam).engine_config(engine).config_hash()


def _args(p: dict[str, Path], tmp_path: Path, *extra: str) -> list[str]:
    return [
        "eval",
        "--split", "test",
        "--manifest", str(p["m"]),
        "--truth", str(p["t"]),
        "--camera-config", str(p["cam"]),
        "--from-observations", str(p["obs"]),
        "--runs-dir", str(tmp_path / "runs"),
        "--frozen-file", str(tmp_path / "frozen-config.txt"),
        "--out", str(tmp_path / "final-eval.local.md"),
        *extra,
    ]  # fmt: skip


def test_eval_test_split_requires_frozen(tmp_path: Path) -> None:
    p = _setup(tmp_path)
    result = cli.invoke(app, _args(p, tmp_path))
    assert result.exit_code != 0
    assert "--frozen" in result.output
    assert not (tmp_path / "runs").exists()


def test_eval_test_split_rejects_hash_mismatch(tmp_path: Path) -> None:
    """Sửa 1 ngưỡng sau khi chốt → hash hiện tại khác `--frozen` → từ chối, không chạy."""
    p = _setup(tmp_path)
    frozen = _hash(p["cam"])
    data = yaml.safe_load(ENGINE.read_text(encoding="utf-8"))
    data["abnormal_movement"]["hold_after_s"] = 9.0
    changed = tmp_path / "engine.changed.yaml"
    changed.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert _hash(p["cam"], changed) != frozen
    result = cli.invoke(
        app, [*_args(p, tmp_path, "--frozen", frozen), "--engine-config", str(changed)]
    )
    assert result.exit_code != 0
    assert "config_hash" in result.output
    assert not (tmp_path / "runs").exists()


def test_eval_test_split_rejects_stale_run_events(tmp_path: Path) -> None:
    """`runs/` còn sự kiện của cấu hình cũ → từ chối (không trộn kết quả hai cấu hình)."""
    p = _setup(tmp_path)
    old = tmp_path / "runs" / VIDEO
    old.mkdir(parents=True)
    (old / "events.jsonl").write_text(json.dumps({"config_hash": "old-hash"}) + "\n", "utf-8")
    result = cli.invoke(app, _args(p, tmp_path, "--frozen", _hash(p["cam"])))
    assert result.exit_code != 0
    assert "old-hash" in result.output


def test_eval_test_split_rejects_frozen_file_mismatch(tmp_path: Path) -> None:
    p = _setup(tmp_path)
    (tmp_path / "frozen-config.txt").write_text("config_hash: abc123\n", encoding="utf-8")
    result = cli.invoke(app, _args(p, tmp_path, "--frozen", _hash(p["cam"])))
    assert result.exit_code != 0
    assert "abc123" in result.output


def test_eval_test_split_runs_with_matching_hash(tmp_path: Path) -> None:
    p = _setup(tmp_path)
    frozen = _hash(p["cam"])
    result = cli.invoke(app, _args(p, tmp_path, "--frozen", frozen))
    assert result.exit_code == 0, result.output
    md = (tmp_path / "final-eval.local.md").read_text(encoding="utf-8")
    assert frozen in md
    assert (tmp_path / "final-eval.local.json").is_file()
    # Lần chạy đầu ghi file chốt nếu chưa có.
    assert read_frozen_hash(tmp_path / "frozen-config.txt") == frozen
    assert run_dir_hashes(tmp_path / "runs" / VIDEO) <= {frozen}


def test_freeze_writes_frozen_config(tmp_path: Path) -> None:
    p = _setup(tmp_path)
    out = tmp_path / "frozen-config.txt"
    args = [
        "eval", "freeze",
        "--split", "test",
        "--manifest", str(p["m"]),
        "--truth", str(p["t"]),
        "--camera-config", str(p["cam"]),
        "--out", str(out),
    ]  # fmt: skip
    result = cli.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert read_frozen_hash(out) == _hash(p["cam"])
    text = out.read_text(encoding="utf-8")
    assert "engine_config" in text and "camera_config" in text


def test_freeze_rejects_multiple_hashes(tmp_path: Path) -> None:
    """Hai video dùng override ngưỡng khác nhau → hai hash → không chốt được (§8 câu hỏi mở)."""
    rows = [
        manifest_row("v1", split="test", duration_s="10"),
        manifest_row("v2", split="test", duration_s="10"),
    ]
    m, t = write_dataset(tmp_path, rows, [])
    cams = tmp_path / "cameras"
    cams.mkdir()
    write_camera_yaml(cams / "v2.yaml", thresholds={"abnormal_movement": {"hold_after_s": 3.0}})
    args = [
        "eval", "freeze",
        "--split", "test",
        "--manifest", str(m),
        "--truth", str(t),
        "--camera-config", str(write_camera_yaml(tmp_path / "cam.yaml")),
        "--cameras-dir", str(cams),
        "--out", str(tmp_path / "frozen-config.txt"),
    ]  # fmt: skip
    result = cli.invoke(app, args)
    assert result.exit_code != 0
    assert not (tmp_path / "frozen-config.txt").exists()
