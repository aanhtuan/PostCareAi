"""Pipeline dùng chung cho worker (F17) và replay (F12): khung hình → adapter → engine.

overview.md §6: "`replay` dùng **chung** pipeline `vision` + `engine` với worker", để kết quả
offline phản ánh đúng realtime. Module này chỉ dựa vào interface `PoseAdapter`, không import
mediapipe; adapter cụ thể do nơi gọi tạo.
"""

from postcare.engine import Engine
from postcare.schemas.events import EngineOutput
from postcare.schemas.observation import FrameObservation
from postcare.vision.camera import Frame
from postcare.vision.inference.base import PoseAdapter

__all__ = ["process_frame"]


def process_frame(
    frame: Frame, adapter: PoseAdapter, engine: Engine
) -> tuple[FrameObservation, EngineOutput]:
    """Chạy adapter pose trên một khung rồi đưa quan sát vào engine.

    `camera_id` lấy từ `engine.context`. Face (F25) bổ sung ở đây khi có face adapter.
    """
    obs = adapter.observe(frame, engine.context.camera_id)
    return obs, engine.process(obs)
