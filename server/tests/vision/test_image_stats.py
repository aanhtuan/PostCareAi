"""F06 R3, R7: độ sáng trung bình (xám 0–255) và nén JPEG thu nhỏ trước khi gửi."""

import cv2
import numpy as np

from postcare.vision.image_stats import mean_brightness
from postcare.vision.render import encode_jpeg


def test_mean_brightness_gray_levels() -> None:
    assert mean_brightness(np.zeros((10, 10, 3), dtype=np.uint8)) == 0.0
    assert mean_brightness(np.full((10, 10, 3), 255, dtype=np.uint8)) == 255.0
    half = np.zeros((10, 10, 3), dtype=np.uint8)
    half[:5] = 200
    assert abs(mean_brightness(half) - 100.0) < 0.5


def test_encode_jpeg_downscales_long_side() -> None:
    image = np.full((1080, 1920, 3), 128, dtype=np.uint8)
    data = encode_jpeg(image, max_side=960, quality=70)
    assert data[:2] == b"\xff\xd8"
    decoded = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape[:2] == (540, 960)


def test_encode_jpeg_keeps_small_frames() -> None:
    image = np.full((48, 64, 3), 50, dtype=np.uint8)
    decoded = cv2.imdecode(np.frombuffer(encode_jpeg(image), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape[:2] == (48, 64)
