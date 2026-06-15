"""
app/utils.py — Shared Helper Utilities
========================================
JSON response builders, timestamp helpers, uptime tracking, and misc tools.
"""

import os
import time
import datetime
from flask import jsonify, request

# ── App start time (set when the Flask app factory runs) ──────────────────────
_APP_START_TIME: float = time.time()


def set_start_time():
    """Call once in the Flask app factory to record startup time."""
    global _APP_START_TIME
    _APP_START_TIME = time.time()


def get_uptime_str() -> str:
    """Return a human-readable uptime string like '2 days 5 hours 30 minutes'."""
    elapsed = int(time.time() - _APP_START_TIME)
    days    = elapsed // 86400
    hours   = (elapsed % 86400) // 3600
    minutes = (elapsed % 3600) // 60
    seconds = elapsed % 60

    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return " ".join(parts)


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO 8601 string with trailing Z."""
    return datetime.datetime.utcnow().isoformat() + "Z"


# ── Response builders ─────────────────────────────────────────────────────────

def success_response(data: dict | None = None, message: str = "OK", status_code: int = 200):
    """Build a standard success JSON response."""
    payload = {"success": True, "message": message, "timestamp": utcnow_iso()}
    if data is not None:
        payload.update(data)
    return jsonify(payload), status_code


def error_response(
    error: str,
    code: str = "ERROR",
    status_code: int = 400,
    errors: list | None = None,
):
    """Build a standard error JSON response."""
    payload = {
        "success":   False,
        "error":     error,
        "code":      code,
        "timestamp": utcnow_iso(),
    }
    if errors:
        payload["errors"] = errors
    return jsonify(payload), status_code


# ── Database size helper ──────────────────────────────────────────────────────

def get_db_size_mb(db_uri: str) -> float | None:
    """
    Estimate database file size in MB.
    Works only for file-based SQLite (returns file size).
    Returns 0.0 for in-memory SQLite (:memory:) and None for MySQL.
    """
    if "sqlite" in db_uri.lower():
        # Extract file path from URI  (sqlite:////path/to/file.db)
        path = db_uri.replace("sqlite:///", "")
        # In-memory SQLite has no real file path
        if not path or path == ":memory:":
            return 0.0
        try:
            size_bytes = os.path.getsize(path)
            return round(size_bytes / (1024 * 1024), 3)
        except (FileNotFoundError, OSError):
            return 0.0
    return None


# ── Remote IP helper ──────────────────────────────────────────────────────────

def get_remote_ip() -> str:
    """Extract the real remote IP, honouring X-Forwarded-For (reverse proxy)."""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"
