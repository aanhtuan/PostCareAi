"""Che giá trị `token=` trong query trước khi ghi log (api-conventions.md, mục xác thực).

MJPEG (F07) và WebSocket (F18) nhận JWT qua `?token=` vì trình duyệt không gửi được header;
access log của uvicorn ghi cả đường dẫn kèm query, nên filter này thay giá trị bằng `***`.
Riêng WebSocket, uvicorn ghi dòng `"WebSocket /api/v1/ws?token=…" [accepted]` qua logger
`uvicorn.error` (không qua access log), nên filter gắn vào cả hai logger (F18).
"""

import logging
import re

_TOKEN_RE = re.compile(r"(?i)([?&]token=)[^&\s\"']*")
ACCESS_LOGGER = "uvicorn.access"
ERROR_LOGGER = "uvicorn.error"  # uvicorn ghi đường dẫn WebSocket ở đây


def redact(text: str) -> str:
    return _TOKEN_RE.sub(r"\1***", text)


class RedactQueryTokenFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        return True


def install_access_log_redaction(*logger_names: str) -> None:
    """Gắn filter vào các logger (mặc định: access log và logger WebSocket; idempotent)."""
    for name in logger_names or (ACCESS_LOGGER, ERROR_LOGGER):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactQueryTokenFilter) for f in logger.filters):
            logger.addFilter(RedactQueryTokenFilter())
