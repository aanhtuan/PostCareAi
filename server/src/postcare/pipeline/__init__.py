"""Pipeline dùng chung cho worker (F06/F17) và replay (F12): khung hình → adapter → engine.

overview.md §6: "`replay` dùng **chung** pipeline `vision` + `engine` với worker", để kết quả
offline phản ánh đúng realtime. Module này chỉ dựa vào interface `PoseAdapter` và `FaceGate`,
không import mediapipe; adapter cụ thể do nơi gọi tạo.
"""

from typing import Protocol

from postcare.engine import Engine
from postcare.schemas.context import EngineContext
from postcare.schemas.events import EngineOutput
from postcare.schemas.observation import FrameObservation, PersonPose
from postcare.vision.camera import Frame
from postcare.vision.inference.base import PoseAdapter
from postcare.vision.inference.face_gate import FaceGate

__all__ = ["FrameEngine", "process_frame"]


class FrameEngine(Protocol):
    """Phần của `Engine` mà pipeline dùng (cho phép engine giả trong test worker)."""

    @property
    def context(self) -> EngineContext: ...

    def process(self, obs: FrameObservation) -> EngineOutput: ...

    def peek_target(self, obs: FrameObservation) -> PersonPose | None:
        """Người mục tiêu mà `process(obs)` sẽ chọn, chỉ đọc (nhánh face F25)."""
        ...


def process_frame(
    frame: Frame,
    adapter: PoseAdapter,
    engine: Engine | FrameEngine,
    face: FaceGate | None = None,
    *,
    face_fallback: bool = False,
) -> tuple[FrameObservation, EngineOutput]:
    """Chạy adapter pose trên một khung, nhánh face (nếu có), rồi đưa quan sát vào engine.

    `camera_id` lấy từ `engine.context`. `face` là `None` khi `face.enabled = false` (F25 R9):
    khi đó `obs.face` luôn `None`. Nhánh face chạy trên người mục tiêu mà engine sắp chọn
    (`Engine.peek_target`) và không bao giờ raise (F25 R8), nên pose/engine không bị gián đoạn.

    `face_fallback` (hồ sơ không gắn giường, F38): engine chưa có mục tiêu (cận cảnh webcam, hông
    ngoài khung) → nhánh face dùng người có vùng đầu lớn nhất. Theo dõi giường để `False`, để không
    đọc mặt người ngoài vùng giường.
    """
    obs = adapter.observe(frame, engine.context.camera_id)
    if face is not None:
        target = engine.peek_target(obs)
        if target is None and face_fallback:
            target = face.most_prominent(obs.persons, (frame.width, frame.height))
        face_obs = face.observe(frame, target)
        if face_obs is not None:
            obs = obs.model_copy(update={"face": face_obs})
    return obs, engine.process(obs)
