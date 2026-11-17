"""Phần dùng chung của các rule (F15, F23): bản nháp sự kiện và `confidence` theo visibility.

`confidence` = trung bình visibility của `pose.required_keypoints` của người mục tiêu trên các frame
trong `[occurred_at_ms, detected_at_ms]` (giả định F15 R9). Thời gian chỉ lấy từ `ts_ms`.
"""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import JsonValue

from postcare.schemas.events import EventCode
from postcare.schemas.observation import KeypointName, PersonPose
from postcare.schemas.state import ObservationQuality

MS_PER_S = 1000

Explanation = dict[str, JsonValue]


@dataclass(frozen=True)
class EventDraft:
    """Sự kiện trước debounce. `RuleSet` gắn `priority` (catalog) và `config_hash`."""

    code: EventCode
    occurred_at_ms: int
    detected_at_ms: int
    confidence: float
    observation_quality: ObservationQuality
    explanation: Explanation


class VisibilityBuffer:
    """Bộ đệm `(ts_ms, visibility trung bình của keypoint bắt buộc)` trong `horizon_ms` gần nhất."""

    def __init__(self, required: Sequence[KeypointName], horizon_ms: float) -> None:
        self._required = tuple(required)
        self._horizon_ms = horizon_ms
        self._values: deque[tuple[int, float]] = deque()

    def record(self, ts_ms: int, target: PersonPose | None) -> None:
        if target is not None:
            values = [
                kp.visibility if (kp := target.keypoints.get(name)) is not None else 0.0
                for name in self._required
            ]
            self._values.append((ts_ms, sum(values) / len(values)))
        while self._values and self._values[0][0] < ts_ms - self._horizon_ms:
            self._values.popleft()

    def confidence(self, start_ms: int, end_ms: int) -> float:
        """Trung bình visibility trong `[start_ms, end_ms]`; không có frame nào → 0.0."""
        values = [v for ts, v in self._values if start_ms <= ts <= end_ms]
        if not values:
            return 0.0
        return round(min(1.0, max(0.0, sum(values) / len(values))), 3)
