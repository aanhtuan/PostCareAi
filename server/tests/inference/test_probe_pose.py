"""F11 R10: thống kê của `postcare probe --pose` (không cần model) và lỗi khi thiếu model."""

from pathlib import Path

from typer.testing import CliRunner

from postcare.cli.main import app
from postcare.schemas.observation import FrameObservation, Keypoint, KeypointName, PersonPose
from postcare.vision.inference.stats import PoseCoverage
from tests.camera.synthetic import write_video

runner = CliRunner()
TORSO = [
    KeypointName.LEFT_SHOULDER,
    KeypointName.RIGHT_SHOULDER,
    KeypointName.LEFT_HIP,
    KeypointName.RIGHT_HIP,
]


def _obs(i: int, persons: list[PersonPose]) -> FrameObservation:
    return FrameObservation(
        camera_id=1, frame_index=i, ts_ms=i, image_size=(64, 48), persons=persons, source_ok=True
    )


def _person(visibility: float, names: list[KeypointName] = TORSO) -> PersonPose:
    return PersonPose(keypoints={n: Keypoint(x=0.5, y=0.5, visibility=visibility) for n in names})


def test_pose_coverage_counts_person_and_torso_frames() -> None:
    cov = PoseCoverage(required=TORSO, min_visibility=0.5)
    cov.add(_obs(0, []))  # không có người
    cov.add(_obs(1, [_person(0.9)]))  # đủ thân
    cov.add(_obs(2, [_person(0.3)]))  # có người, thân mờ
    cov.add(_obs(3, [_person(0.9, TORSO[:3])]))  # thiếu hông phải
    cov.add(_obs(4, [_person(0.2), _person(0.6)]))  # người thứ hai đủ thân
    assert cov.frames == 5
    assert cov.frames_with_person == 4
    assert cov.frames_with_torso == 2
    assert cov.person_ratio == 0.8
    assert cov.torso_ratio == 0.4


def test_pose_coverage_empty_is_zero() -> None:
    cov = PoseCoverage(required=TORSO, min_visibility=0.5)
    assert (cov.person_ratio, cov.torso_ratio) == (0.0, 0.0)


def test_probe_pose_without_model_suggests_make_models(tmp_path: Path) -> None:
    video = write_video(tmp_path / "clip.avi", n_frames=5)
    result = runner.invoke(
        app,
        [
            "probe",
            "--source",
            str(video),
            "--pose",
            "--model",
            "lite",
            "--models-dir",
            str(tmp_path / "khong-co-model"),
        ],
    )
    assert result.exit_code != 0
    assert "make models" in result.output


def test_probe_pose_unknown_variant_fails(tmp_path: Path) -> None:
    video = write_video(tmp_path / "clip.avi", n_frames=5)
    result = runner.invoke(app, ["probe", "--source", str(video), "--pose", "--model", "khong-co"])
    assert result.exit_code != 0
    assert "khong-co" in result.output
