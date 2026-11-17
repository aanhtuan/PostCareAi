"""F16 AC1, AC5, R2: định dạng và validator của manifest.csv / truth.csv (HS §8.1)."""

from pathlib import Path

from postcare.eval.manifest import validate_files

from postcare.schemas.events import EventCode
from tests.eval.helpers import (
    MANIFEST_HEADER,
    manifest_row,
    truth_row,
    write_csv,
    write_dataset,
)


def _errors(tmp_path: Path, manifest: list[dict[str, str]], truth: list[dict[str, str]]) -> str:
    result = validate_files(*write_dataset(tmp_path, manifest, truth))
    assert not result.ok
    return "\n".join(result.errors)


def test_valid_manifest_passes(tmp_path: Path) -> None:
    result = validate_files(
        *write_dataset(
            tmp_path,
            [
                manifest_row("S06_P01_r1"),
                manifest_row("S06_P02_r1", split="test", participant_id="P02", session_id="day2"),
            ],
            [
                truth_row("S06_P01_r1", "BED_EDGE", "20.0", "25.0"),
                truth_row("S06_P01_r1", "BED_EXIT", "27.0", "27.0"),
            ],
        )
    )
    assert result.ok, result.errors
    assert result.warnings == []
    assert [r.video_id for r in result.manifest] == ["S06_P01_r1", "S06_P02_r1"]
    assert result.manifest[0].duration_s == 42.0
    assert [t.event_code for t in result.truth] == [EventCode.BED_EDGE, EventCode.BED_EXIT]


def test_missing_column_rejected(tmp_path: Path) -> None:
    header = [c for c in MANIFEST_HEADER if c != "camera_condition"]
    m = write_csv(tmp_path / "manifest.csv", [manifest_row()], header)
    t = write_csv(tmp_path / "truth.csv", [truth_row()])
    result = validate_files(m, t)
    assert not result.ok
    assert "camera_condition" in "\n".join(result.errors)


def test_bad_split_rejected(tmp_path: Path) -> None:
    assert "split" in _errors(tmp_path, [manifest_row(split="train")], [])


def test_unknown_event_code_rejected(tmp_path: Path) -> None:
    errors = _errors(tmp_path, [manifest_row()], [truth_row(event_code="FALL_DOWN")])
    assert "FALL_DOWN" in errors


def test_start_after_end_rejected(tmp_path: Path) -> None:
    errors = _errors(tmp_path, [manifest_row()], [truth_row(start_s="10", end_s="5")])
    assert "start_s" in errors


def test_time_beyond_duration_rejected(tmp_path: Path) -> None:
    errors = _errors(
        tmp_path, [manifest_row(duration_s="30")], [truth_row(start_s="28", end_s="31")]
    )
    assert "duration_s" in errors


def test_truth_references_unknown_video_rejected(tmp_path: Path) -> None:
    errors = _errors(tmp_path, [manifest_row("S06_P01_r1")], [truth_row("S99_P09_r9")])
    assert "S99_P09_r9" in errors


def test_video_in_both_splits_rejected(tmp_path: Path) -> None:
    errors = _errors(
        tmp_path,
        [manifest_row("S06_P01_r1", split="dev"), manifest_row("S06_P01_r1", split="test")],
        [],
    )
    assert "S06_P01_r1" in errors


def test_same_path_two_ids_rejected(tmp_path: Path) -> None:
    errors = _errors(
        tmp_path,
        [
            manifest_row("S06_P01_r1", path="data/videos/a.mp4"),
            manifest_row("S06_P01_r2", path="data/videos/a.mp4", split="test"),
        ],
        [],
    )
    assert "data/videos/a.mp4" in errors


def test_participant_overlap_is_warning_only(tmp_path: Path) -> None:
    result = validate_files(
        *write_dataset(
            tmp_path,
            [
                manifest_row("S06_P01_r1", split="dev"),
                manifest_row("S06_P01_r2", split="test"),  # cùng P01, cùng day1
            ],
            [],
        )
    )
    assert result.ok, result.errors
    text = "\n".join(result.warnings)
    assert "P01" in text
    assert "day1" in text


def test_eval_codes_and_scenario_parsed_from_notes(tmp_path: Path) -> None:
    notes = "scenario=S15(nga xuong san);eval_codes=ABNORMAL_MOVEMENT;mo_ta=x"
    result = validate_files(*write_dataset(tmp_path, [manifest_row("urfd_01", notes=notes)], []))
    assert result.ok, result.errors
    row = result.manifest[0]
    assert row.eval_codes == frozenset({EventCode.ABNORMAL_MOVEMENT})
    assert row.scenario == "S15"


def test_scenario_falls_back_to_video_id_prefix(tmp_path: Path) -> None:
    result = validate_files(*write_dataset(tmp_path, [manifest_row("S06_P01_r1")], []))
    row = result.manifest[0]
    assert row.scenario == "S06"
    assert row.eval_codes is None


def test_unknown_eval_code_in_notes_rejected(tmp_path: Path) -> None:
    errors = _errors(tmp_path, [manifest_row(notes="eval_codes=SIT_UP,FALL")], [])
    assert "FALL" in errors


def test_external_columns_are_read(tmp_path: Path) -> None:
    row = {**manifest_row("urfd_01"), "source": "URFD", "license": "CC BY-NC-SA 4.0"}
    m = write_csv(tmp_path / "manifest.csv", [row], [*MANIFEST_HEADER, "source", "license"])
    t = write_csv(
        tmp_path / "truth.csv",
        [{**truth_row("urfd_01", "ABNORMAL_MOVEMENT", "2", "3"), "label_source": "dataset"}],
    )
    result = validate_files(m, t)
    assert result.ok, result.errors
    assert result.manifest[0].source == "URFD"
    assert result.truth[0].label_source == "dataset"
