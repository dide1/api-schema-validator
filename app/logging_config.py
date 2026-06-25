"""Structured JSON logging for CloudWatch. Call setup_logging() once at startup."""

import json
import logging
import logging.config
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Per-request context propagated to every log record automatically.
_request_id: ContextVar[str] = ContextVar("request_id", default="-")
_user_id: ContextVar[str] = ContextVar("user_id", default="-")
_user_email: ContextVar[str] = ContextVar("user_email", default="-")

# Keys present on every LogRecord — excluded so `extra={}` fields surface cleanly.
_RECORD_BUILTIN_KEYS: frozenset[str] = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
) | {"message", "asctime"}


def set_request_context(
    request_id: str,
    user_id: str = "-",
    user_email: str = "-",
) -> None:
    _request_id.set(request_id)
    _user_id.set(user_id)
    _user_email.set(user_email)


def get_request_id() -> str:
    return _request_id.get()


class _CloudWatchFormatter(logging.Formatter):
    """One JSON object per line — CloudWatch Logs Insights can query every field."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _request_id.get(),
            "user_id": _user_id.get(),
            "user_email": _user_email.get(),
            "function": f"{record.module}.{record.funcName}",
            "line": record.lineno,
        }

        # Merge caller-supplied extra={} fields.
        for key, value in record.__dict__.items():
            if key not in _RECORD_BUILTIN_KEYS:
                entry[key] = value

        if record.exc_info and record.exc_info[0] is not None:
            entry["error_type"] = record.exc_info[0].__name__
            entry["traceback"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str)


def setup_logging(level: int = logging.INFO, is_lambda: bool = False) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    # Clear handlers so Lambda warm-starts don't duplicate output.
    root.handlers.clear()

    handler = logging.StreamHandler()
    if is_lambda:
        handler.setFormatter(_CloudWatchFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")
        )
    root.addHandler(handler)

    # Silence noisy third-party loggers.
    logging.getLogger("mangum").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
