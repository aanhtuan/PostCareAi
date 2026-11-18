"""Token trong query (`?token=` của MJPEG F07, WS F18) không được ghi vào access log."""

import logging

from postcare.api.log_redaction import (
    RedactQueryTokenFilter,
    install_access_log_redaction,
    redact,
)

from postcare.api.main import create_app
from postcare.settings import Settings


def test_redact_replaces_token_values() -> None:
    assert redact("/api/v1/cameras/1/stream.mjpeg?token=abc.def-ghi") == (
        "/api/v1/cameras/1/stream.mjpeg?token=***"
    )
    assert redact("/api/v1/ws?n=1&token=x.y.z&b=2") == "/api/v1/ws?n=1&token=***&b=2"
    assert redact("/api/v1/beds?limit=5") == "/api/v1/beds?limit=5"


def test_filter_redacts_uvicorn_access_record_args() -> None:
    # uvicorn.access: '%s - "%s %s HTTP/%s" %d', args (client, method, path, version, status).
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:5000", "GET", "/api/v1/cameras/1/stream.mjpeg?token=secret.jwt", "1.1", 200),
        None,
    )
    assert RedactQueryTokenFilter().filter(record) is True
    message = record.getMessage()
    assert "secret.jwt" not in message
    assert "token=***" in message
    assert message.endswith(" 200")


def test_filter_redacts_plain_message() -> None:
    record = logging.LogRecord(
        "x", logging.INFO, __file__, 1, "GET /api/v1/ws?token=secret 101", None, None
    )
    RedactQueryTokenFilter().filter(record)
    assert "secret" not in record.getMessage()


def test_install_is_idempotent() -> None:
    logger = logging.getLogger("uvicorn.access")
    install_access_log_redaction()
    install_access_log_redaction()
    assert sum(isinstance(f, RedactQueryTokenFilter) for f in logger.filters) == 1


def test_app_installs_redaction(settings: Settings) -> None:
    logger = logging.getLogger("uvicorn.access")
    for f in [f for f in logger.filters if isinstance(f, RedactQueryTokenFilter)]:
        logger.removeFilter(f)
    app = create_app(settings, watch_cameras=False)
    app.state.engine.dispose()
    assert any(isinstance(f, RedactQueryTokenFilter) for f in logger.filters)
