import json
import logging
import sys

import pytest

from config.logging_config import (
    JsonFormatter,
    configure_logging,
)


def test_json_formatter_includes_request_context() -> None:
    record = logging.LogRecord(
        name="api.main",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="HTTP request completed.",
        args=(),
        exc_info=None,
    )

    record.request_id = "test-request-id"
    record.method = "GET"
    record.path = "/health/live"
    record.status_code = 200
    record.duration_ms = 1.25

    payload = json.loads(
        JsonFormatter().format(record)
    )

    assert payload["level"] == "INFO"
    assert payload["logger"] == "api.main"
    assert payload["message"] == (
        "HTTP request completed."
    )
    assert payload["request_id"] == "test-request-id"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health/live"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 1.25
    assert payload["timestamp"]


def test_json_formatter_includes_exception() -> None:
    try:
        raise ValueError("Synthetic failure.")
    except ValueError:
        exception_info = sys.exc_info()

    record = logging.LogRecord(
        name="api.main",
        level=logging.ERROR,
        pathname=__file__,
        lineno=10,
        msg="Request failed.",
        args=(),
        exc_info=exception_info,
    )

    payload = json.loads(
        JsonFormatter().format(record)
    )

    assert "ValueError: Synthetic failure." in (
        payload["exception"]
    )


def test_configure_logging_rejects_invalid_level() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported logging level",
    ):
        configure_logging("verbose")