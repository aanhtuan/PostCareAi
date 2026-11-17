"""Tiện ích test F05: video tổng hợp (chỉ hình khối, không có người) và đồng hồ giả.

Video chỉ tạo trong `tmp_path` của pytest, không commit media (AGENTS.md quy tắc 8).
"""

from pathlib import Path

import cv2
import numpy as np


def write_video(
    path: Path, *, n_frames: int = 30, fps: float = 30.0, size: tuple[int, int] = (64, 48)
) -> Path:
    """Ghi file AVI/MJPG: mỗi khung là một ô vuông trắng dịch dần trên nền xám."""
    width, height = size
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width, height))
    assert writer.isOpened(), "VideoWriter MJPG không mở được"
    for i in range(n_frames):
        image = np.full((height, width, 3), 80, dtype=np.uint8)
        x = (i * 2) % max(width - 8, 1)
        image[10:18, x : x + 8] = 255
        writer.write(image)
    writer.release()
    return path


class FakeClock:
    """Đồng hồ đơn điệu giả: `sleep` chỉ cộng thời gian, không chờ thật."""

    def __init__(self) -> None:
        self.now_ns = 1_000_000_000
        self.sleeps: list[float] = []

    def __call__(self) -> int:
        return self.now_ns

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now_ns += int(seconds * 1_000_000_000)

    def advance_ms(self, ms: int) -> None:
        self.now_ns += ms * 1_000_000
