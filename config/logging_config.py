import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


STRUCTURED_FIELDS = (
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
)


class JsonFormatter(logging.Formatter):
    """Format application logs as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=UTC,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field_name in STRUCTURED_FIELDS:
            if hasattr(record, field_name):
                payload[field_name] = getattr(
                    record,
                    field_name,
                )

        if record.exc_info:
            payload["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(
            payload,
            ensure_ascii=False,
        )


def configure_logging(level: str = "INFO") -> None:
    """Configure consistent JSON application logging."""

    normalized_level = level.strip().upper()

    if normalized_level not in {
        "CRITICAL",
        "ERROR",
        "WARNING",
        "INFO",
        "DEBUG",
    }:
        raise ValueError(
            f"Unsupported logging level: {level}"
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(normalized_level)

    # Request middleware provides richer access logs.
    logging.getLogger("uvicorn.access").disabled = True

    logging.captureWarnings(True)