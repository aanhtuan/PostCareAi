"""Số liệu ảnh đơn giản cho heartbeat worker (F06 R3): độ sáng trung bình 0–255 của ảnh xám.

Phục vụ chỉ báo "thiếu sáng" ở F08 (PDF §9.1). Không phải ngưỡng engine.
"""

from __future__ import annotations

import cv2
import numpy as np

from postcare.vision.camera import Image


def mean_brightness(image: Image) -> float:
    """Trung bình mức xám (0–255) của khung BGR (hoặc ảnh xám một kênh)."""
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray))
