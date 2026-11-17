"""F12 AC4: cắt đoạn observation thành fixture chỉ toạ độ + `.expected.json`."""

import json
from pathlib import Path

from typer.testing import CliRunner

from postcare.cli.main import app
from postcare.replay.fixtures import discover_fixtures, run_fixture
from postcare.schemas.observation import FrameObservation
from tests.replay.helpers import DEFAULT_ENGINE, scenario, write_camera_yaml, write_observations

cli = CliRunner()


def _cut(tmp_path: Path, *extra: str) -> tuple[int, str, Path]:
    obs = write_observations(tmp_path / "obs.jsonl", scenario())
    cam = write_camera_yaml(tmp_path / "cam.yaml")
    target = tmp_path / "fixtures" / "s03_sit_lie.jsonl"
    result = cli.invoke(
        app,
        [
            "replay",
            "--from-observations",
            str(obs),
            "--camera-config",
            str(cam),
            "--save-observations",
            str(target),
            *extra,
        ],
    )
    return result.exit_code, result.output, target


def test_fixture_cut_range(tmp_path: Path) -> None:
    code, output, target = _cut(tmp_path, "--start-s", "2", "--end-s", "5.5", "--save-expected")
    assert code == 0, output
    lines = target.read_text(encoding="utf-8").splitlines()
    cut = [FrameObservation.model_validate_json(line) for line in lines]
    expected_ts = [o.ts_ms for o in scenario() if 2000 <= o.ts_ms <= 5500]
    assert [o.ts_ms for o in cut] == expected_ts
    expected = json.loads(target.with_suffix(".expected.json").read_text(encoding="utf-8"))
    assert set(expected) >= {"camera", "range_s", "config_hash", "events"}
    assert expected["range_s"] == [2.0, 5.5]
    assert isinstance(expected["events"], list)
    for event in expected["events"]:
        assert set(event) == {"code", "occurred_at_ms"}


def test_fixture_contains_only_observation_fields(tmp_path: Path) -> None:
    code, output, target = _cut(tmp_path, "--save-expected")
    assert code == 0, output
    allowed = set(FrameObservation.model_fields)
    text = target.read_text(encoding="utf-8")
    for line in text.splitlines():
        assert set(json.loads(line)) <= allowed
    expected_text = target.with_suffix(".expected.json").read_text(encoding="utf-8")
    for blob in (text, expected_text):
        assert "obs.jsonl" not in blob
        assert ".mp4" not in blob and ".avi" not in blob
        assert str(tmp_path) not in blob and str(tmp_path).replace("\\", "/") not in blob


def test_fixture_cut_rejects_inverted_range(tmp_path: Path) -> None:
    code, output, target = _cut(tmp_path, "--start-s", "5", "--end-s", "2")
    assert code != 0
    assert "--start-s" in output
    assert not target.exists()


def test_fixture_cut_rejects_empty_range(tmp_path: Path) -> None:
    code, output, _ = _cut(tmp_path, "--start-s", "100", "--end-s", "200")
    assert code != 0
    assert "Không có observation" in output


def test_save_expected_requires_save_observations(tmp_path: Path) -> None:
    obs = write_observations(tmp_path / "obs.jsonl", scenario())
    cam = write_camera_yaml(tmp_path / "cam.yaml")
    result = cli.invoke(
        app,
        ["replay", "--from-observations", str(obs), "--camera-config", str(cam), "--save-expected"],
    )
    assert result.exit_code != 0


def test_cut_fixture_passes_regression(tmp_path: Path) -> None:
    code, output, target = _cut(tmp_path, "--save-expected")
    assert code == 0, output
    cases = discover_fixtures(target.parent)
    assert [c.name for c in cases] == ["s03_sit_lie"]
    actual, expected = run_fixture(cases[0], DEFAULT_ENGINE)
    assert actual == expected


def test_fixture_without_expected_is_reported(tmp_path: Path) -> None:
    write_observations(tmp_path / "a.jsonl", scenario()[:5])
    write_observations(tmp_path / "b.jsonl", scenario()[:5])
    (tmp_path / "a.expected.json").write_text(
        json.dumps(
            {
                "camera": {
                    "version": 1,
                    "camera_id": 1,
                    "roi_polygon": [[0.2, 0.3], [0.8, 0.3], [0.8, 0.8], [0.2, 0.8]],
                },
                "range_s": None,
                "config_hash": "x",
                "events": [],
            }
        ),
        encoding="utf-8",
    )
    cases = {c.name: c for c in discover_fixtures(tmp_path)}
    assert set(cases) == {"a", "b"}
    assert cases["a"].expected is not None
    assert cases["b"].expected is None
    assert "expected.json" in cases["b"].skip_reason


def test_discover_empty_dir(tmp_path: Path) -> None:
    assert discover_fixtures(tmp_path) == []
    assert discover_fixtures(tmp_path / "missing") == []
