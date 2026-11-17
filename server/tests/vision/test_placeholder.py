"""Test giữ chỗ cho marker `vision` (F00 bước 3).

`pytest -m vision` trả exit 5 khi không thu được test nào; test này giữ cho `make test-vision`
trả exit 0 cho tới khi F11 thêm test chạy model MediaPipe thật.
"""

import pytest


@pytest.mark.vision
def test_vision_placeholder() -> None:
    pytest.skip("Chưa có test vision: F11 thêm model MediaPipe và video thật")
