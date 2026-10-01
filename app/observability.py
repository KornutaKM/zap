import json
import logging
from datetime import datetime, timezone
from typing import Any


SENSITIVE_FRAGMENTS = (
    "token",
    "secret",
    "password",
    "authorization",
    "api_key",
    "apikey",
    "vin",
)


def _redact(value: Any, key: str | None = None) -> Any:
    if key and any(fragment in key.casefold() for fragment in SENSITIVE_FRAGMENTS):
        return "***"

    if isinstance(value, dict):
        return {
            str(item_key): _redact(item_value, str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        event = getattr(record, "event", None)
        if event:
            payload["event"] = event

        data = getattr(record, "data", None)
        if isinstance(data, dict):
            payload["data"] = _redact(data)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    numeric = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(numeric)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    message: str,
    **data: Any,
) -> None:
    logger.log(
        level,
        message,
        extra={
            "event": event,
            "data": _redact(data),
        },
    )
