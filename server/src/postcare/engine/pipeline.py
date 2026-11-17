"""Các bước pipeline của engine (event-engine.md mục 3) chưa tách ra module riêng.

- Bước 1 chọn người mục tiêu: `engine/target.py` (F13).
- Bước 2 tính đặc trưng: `engine/features.py` (F13).
- Bước 3 làm mượt + chất lượng: `engine/smoothing.py`, `engine/quality.py` (F13).
- Bước 4–5 tư thế thô + state machine: `engine/posture.py`, `engine/state_machine.py` (F14).
- Bước 6–9 rule, vận động, khuôn mặt, debounce: `RuleSet` ở `engine/rules/` (F15, F23, F26, F27).

Mọi bước là thuần: chỉ nhận dữ liệu và `ts_ms`, không đọc đồng hồ hệ thống, không I/O.
"""

from dataclasses import dataclass

from postcare.engine.features import BodyFeatures
from postcare.schemas.observation import PersonPose
from postcare.schemas.state import ObservationQuality


@dataclass(frozen=True)
class FrameAssessment:
    """Kết quả bước 1–3 cho một khung hình."""

    quality: ObservationQuality
    """Chất lượng của riêng frame này (R6)."""
    target: PersonPose | None
    features: BodyFeatures | None
    """Đặc trưng đã làm mượt; chỉ có khi `quality = GOOD` (R7, R8)."""
    observable: bool
    """Cổng chất lượng đang mở (R7). False → engine báo `NO_OBSERVATION`."""
    persons_in_roi: int
    target_is_new: bool = False
    """True khi frame này vừa nhận người mục tiêu mới (F13 `TargetSelection.is_new`; F23 R8)."""
