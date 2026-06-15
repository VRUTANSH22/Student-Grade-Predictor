"""
app/logger.py — Structured JSON Logging
=========================================
Configures a daily-rotating JSON log file and a console handler.
Every log record is emitted as a single JSON object (JSONL format).

Usage:
    from app.logger import setup_logging, get_logger
    setup_logging(log_dir="logs")
    logger = get_logger(__name__)
    logger.info("msg", extra={"student_id": "STU001"})
"""

import os
import json
import logging
import datetime
from logging.handlers import TimedRotatingFileHandler


class JSONFormatter(logging.Formatter):
    """
    Formats log records as compact JSON objects.
    Extra fields attached via `extra={...}` are merged into the top-level dict.
    """

    # Fields we always include
    BASE_FIELDS = {
        "timestamp", "log_level", "logger", "message",
        "filename", "lineno", "funcName",
    }

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp":  datetime.datetime.utcnow().isoformat() + "Z",
            "log_level":  record.levelname,
            "logger":     record.name,
            "message":    record.getMessage(),
            "filename":   record.filename,
            "lineno":     record.lineno,
            "funcName":   record.funcName,
        }

        # Merge any extra fields (e.g. student_id, execution_time_ms, …)
        for key, val in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and key not in (
                "message", "asctime", "args", "exc_info", "exc_text",
                "stack_info", "msg", "levelname", "levelno", "name",
                "pathname", "filename", "module", "lineno", "funcName",
                "created", "msecs", "relativeCreated", "thread",
                "threadName", "processName", "process",
            ):
                entry[key] = val

        # Include exception traceback if present
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str)


class ColorConsoleFormatter(logging.Formatter):
    """Simple coloured console formatter for readability during development."""

    COLORS = {
        "DEBUG":    "\033[94m",   # blue
        "INFO":     "\033[92m",   # green
        "WARNING":  "\033[93m",   # yellow
        "ERROR":    "\033[91m",   # red
        "CRITICAL": "\033[41m",   # red background
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts    = datetime.datetime.utcnow().strftime("%H:%M:%S")
        return (
            f"{color}[{ts}] {record.levelname:<8}{self.RESET} "
            f"{record.name}: {record.getMessage()}"
        )


def setup_logging(log_dir: str = "logs", level: int = logging.INFO):
    """
    Initialise the root logger with:
      - A daily-rotating JSON file handler  (logs/app_YYYY-MM-DD.json)
      - A coloured console handler

    Call once in the Flask app factory.
    """
    os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # ── Avoid adding duplicate handlers on Flask reloader double-init ──
    if root_logger.handlers:
        return

    # ── File handler (JSONL, daily rotation, keep 30 days) ──────────────
    log_filename = os.path.join(log_dir, "app.json")
    file_handler = TimedRotatingFileHandler(
        filename    = log_filename,
        when        = "midnight",
        interval    = 1,
        backupCount = 30,
        encoding    = "utf-8",
        utc         = True,
    )
    # Rename rotated files to  app_YYYY-MM-DD.json
    file_handler.suffix   = "%Y-%m-%d"
    file_handler.namer    = lambda name: name.replace(".json.", "_") + ".json"
    file_handler.setFormatter(JSONFormatter())
    file_handler.setLevel(level)

    # ── Console handler ──────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorConsoleFormatter())
    console_handler.setLevel(logging.DEBUG)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Silence overly verbose third-party loggers
    for noisy in ("urllib3", "werkzeug", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (wrapper for logging.getLogger)."""
    return logging.getLogger(name)
