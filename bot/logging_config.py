"""
Structured logging configuration.
- File handler: JSON-formatted logs for machine readability and auditability.
- Console handler: Human-readable (suppressed in normal Rich UI usage).
"""

import logging
import json
import os
from datetime import datetime, timezone
from pathlib import Path


LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "trading_bot.log"


class JSONFormatter(logging.Formatter):
    """Emits one JSON object per log line — structured, grep-able, auditable."""

    SKIP_FIELDS = {"msg", "message", "args", "exc_info", "exc_text", "stack_info"}

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }
        # Attach any extra fields passed via `extra=` or direct record attributes.
        for key, val in record.__dict__.items():
            if key.startswith("_") or key in self.SKIP_FIELDS or key in payload:
                continue
            if key in {
                "name", "pathname", "filename", "module", "funcName",
                "lineno", "created", "relativeCreated", "thread",
                "threadName", "processName", "process", "levelno", "msecs",
            }:
                continue
            payload[key] = val

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def setup_logging(log_level: str = "DEBUG") -> logging.Logger:
    """
    Configure root logger.
    Returns the root 'trading_bot' logger.
    """
    logger = logging.getLogger("trading_bot")
    logger.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))

    if not logger.handlers:
        # --- File handler (JSON) ---
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(JSONFormatter())
        logger.addHandler(fh)

        # --- Optional plain console handler (disabled by default; Rich handles UI) ---
        # Uncomment below to also print raw logs to stderr:
        # sh = logging.StreamHandler()
        # sh.setLevel(logging.WARNING)
        # sh.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        # logger.addHandler(sh)

    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'trading_bot' namespace."""
    return logging.getLogger(f"trading_bot.{name}")
