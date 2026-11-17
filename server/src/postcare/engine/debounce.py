"""Bước 9 (phần debounce): chặn phát lại cùng khóa trong một cửa sổ thời gian (F15 R8).

Dùng chung cho rule cơ thể (F15), vận động (F23), khuôn mặt (F26). Phạm vi "cùng phiên" là vòng
đời của instance sở hữu nó (một `Engine`; event-engine.md mục 7). Thời gian chỉ lấy từ `ts_ms`.
"""

MS_PER_S = 1000


class Debouncer:
    """Cho phát `key` khi chưa phát lần nào hoặc đã qua ≥ `window_s` kể từ lần **phát** gần nhất."""

    def __init__(self, window_s: float) -> None:
        self._window_ms = window_s * MS_PER_S
        self._last_emitted_ms: dict[str, int] = {}

    def allow(self, key: str, ts_ms: int) -> bool:
        """True → được phát và ghi mốc mới; False → bị chặn, mốc giữ nguyên."""
        last = self._last_emitted_ms.get(key)
        if last is not None and ts_ms - last < self._window_ms:
            return False
        self._last_emitted_ms[key] = ts_ms
        return True
