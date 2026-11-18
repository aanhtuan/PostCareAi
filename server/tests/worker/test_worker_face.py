"""F25 R7–R9 + F06: worker truyền cổng face vào `process_frame`; lỗi face không đổi luồng cơ thể."""

from __future__ import annotations

from pathlib import Path

from postcare.schemas.enums import FaceStatus
from postcare.schemas.observation import PersonPose
from postcare.settings import REPO_ROOT
from postcare.vision.inference.face_gate import FaceGate
from postcare.worker.config import WorkerConfig
from postcare.worker.loop import default_face_factory
from tests.face.helpers import FakeFaceDetector, face_config, head_person
from tests.worker.helpers import Harness, make_harness

ENGINE_YAML = REPO_ROOT / "config" / "engine.default.yaml"


def _person(_i: int) -> list[PersonPose]:
    return [head_person(60.0)]


def _run(detector: FakeFaceDetector | None) -> tuple[Harness, list[FaceGate]]:
    gates: list[FaceGate] = []

    def factory(cfg: WorkerConfig) -> FaceGate | None:
        if detector is None:
            return None
        # Khung giả 64×48 px: vùng đầu ~13 px, nên hạ ngưỡng để cổng gọi landmarker.
        gate = FaceGate.from_config(face_config(min_head_box_px=1), detector)
        gates.append(gate)
        return gate

    h = make_harness(persons=_person, face_factory=factory)
    h.run_until(3.0)
    return h, gates


def test_worker_passes_face_gate_to_pipeline() -> None:
    detector = FakeFaceDetector({})
    h, gates = _run(detector)
    engine = h.engines[0]
    assert detector.calls, "worker phải chạy face trên người mục tiêu"
    ran = [f for f in engine.faces if f is not None]
    assert ran and all(f.status == FaceStatus.OK for f in ran)
    # run_every_n_frames = 2 (A05): một nửa khung không chạy face.
    assert engine.faces[1] is None
    assert len(gates) == 1


def test_worker_face_error_does_not_change_body_flow() -> None:
    broken, gates = _run(FakeFaceDetector(error=RuntimeError("face hỏng")))
    plain, _ = _run(None)
    assert gates[0].error_count > 0
    assert broken.engines[0].processed == plain.engines[0].processed
    assert broken.api.paths("/state") == plain.api.paths("/state")
    assert broken.api.calls == plain.api.calls  # heartbeat, state, frame, event: giống hệt
    assert all(f is None for f in plain.engines[0].faces)


def test_worker_face_factory_error_keeps_body_running() -> None:
    def broken_factory(cfg: WorkerConfig) -> FaceGate | None:
        raise RuntimeError("không mở được model face")

    h = make_harness(persons=_person, face_factory=broken_factory)
    h.run_until(2.0)
    assert h.engines and h.engines[0].processed
    assert all(f is None for f in h.engines[0].faces)


def test_default_face_factory_respects_enabled_and_missing_model(tmp_path: Path) -> None:
    cfg = WorkerConfig.model_validate(
        {
            "camera_id": 1,
            "bed_id": 1,
            "source_type": "FILE",
            "source": "fake.mp4",
            "roi_polygon": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.9]],
            "thresholds": {"face": {"enabled": False}},
            "display_mode": "RAW",
            "config_version": 1,
            "active_session_id": None,
            "capture_paused": False,
        }
    )
    make = default_face_factory(ENGINE_YAML, tmp_path)
    assert make(cfg) is None
    enabled = cfg.model_copy(update={"thresholds": {}})
    gate = make(enabled)  # thiếu model trong tmp_path → cổng không adapter (NOT_VISIBLE, R8)
    assert gate is not None
    gate.close()
