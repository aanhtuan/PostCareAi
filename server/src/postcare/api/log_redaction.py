"""Che giá trị `token=` trong query trước khi ghi log (api-conventions.md, mục xác thực).

MJPEG (F07) và WebSocket (F18) nhận JWT qua `?token=` vì trình duyệt không gửi được header;
access log của uvicorn ghi cả đường dẫn kèm query, nên filter này thay giá trị bằng `***`.
"""

import logging
import re

_TOKEN_RE = re.compile(r"(?i)([?&]token=)[^&\s\"']*")
ACCESS_LOGGER = "uvicorn.access"


def redact(text: str) -> str:
    return _TOKEN_RE.sub(r"\1***", text)


class RedactQueryTokenFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        return True


def install_access_log_redaction(logger_name: str = ACCESS_LOGGER) -> None:
    """Gắn filter vào logger (idempotent)."""
    logger = logging.getLogger(logger_name)
    if not any(isinstance(f, RedactQueryTokenFilter) for f in logger.filters):
        logger.addFilter(RedactQueryTokenFilter())
