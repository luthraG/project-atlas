"""Structured logging: one JSON object per line, for log shipping.

Enabled with ``LOG_FORMAT=json`` (optionally ``LOG_FILE=<path>``); the
default leaves Python's logging untouched, as uvicorn configures it.
"""

import json
import logging
import sys
import traceback
from datetime import UTC, datetime

# LogRecord attributes that are not user-supplied ``extra`` fields.
_RESERVED = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    # Innermost frames only: they locate the failure, and the record stays small enough to ship.
    traceback_frames = 5

    def formatException(self, ei) -> str:  # noqa: N802 - logging.Formatter API
        return "".join(traceback.format_exception(*ei, limit=-self.traceback_frames)).rstrip()

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _RESERVED and not key.startswith("_"):
                entry[key] = value
        if record.exc_info and record.exc_info[1] is not None:
            entry["error_type"] = type(record.exc_info[1]).__name__
            entry["error"] = str(record.exc_info[1])
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(log_format: str, log_file: str | None = None) -> None:
    if log_format != "json":
        return
    handler: logging.Handler = (
        logging.FileHandler(log_file, encoding="utf-8") if log_file else logging.StreamHandler(sys.stdout)
    )
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    # Server notices share the same stream and format.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True
