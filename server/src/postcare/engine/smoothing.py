"""Bước 3a: làm mượt EMA vị trí keypoint (F13 R4; event-engine.md mục 3).

`smoothed = alpha × mới + (1 − alpha) × cũ`, hệ số `smoothing.ema_alpha`. Điểm vắng mặt ở một
frame (keypoint không thấy) thì bỏ giá trị cũ của điểm đó, để lần thấy lại không bị kéo về vị trí
đã lỗi thời *(giả định)*.
"""

from collections.abc import Mapping

from postcare.engine.geometry import Px


class PointSmoother:
    """EMA cho một tập điểm có tên. `reset()` khi đổi người mục tiêu hoặc thoát NO_OBSERVATION."""

    def __init__(self, alpha: float) -> None:
        self._alpha = alpha
        self._state: dict[str, Px] = {}

    def reset(self) -> None:
        self._state.clear()

    def update(self, points: Mapping[str, Px | None]) -> dict[str, Px | None]:
        a = self._alpha
        out: dict[str, Px | None] = {}
        for name, p in points.items():
            if p is None:
                self._state.pop(name, None)
                out[name] = None
                continue
            prev = self._state.get(name)
            smoothed = (
                p if prev is None else (a * p[0] + (1 - a) * prev[0], a * p[1] + (1 - a) * prev[1])
            )
            self._state[name] = smoothed
            out[name] = smoothed
        return out
