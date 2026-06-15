"""
app/validators.py — Input Validation
======================================
Validates all incoming API request payloads and returns structured error lists.
All validation is purely in Python (no third-party validation library required).
"""

import re
from typing import Tuple, List

# ── Field rules ───────────────────────────────────────────────────────────────

STUDENT_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{3,20}$")

FIELD_RULES = {
    "attendance_percentage": {"type": float, "min": 0.0,  "max": 100.0},
    "study_hours_per_week":  {"type": float, "min": 0.0,  "max": 168.0},
    "assignment_score":      {"type": float, "min": 0.0,  "max": 100.0},
    "quiz_marks":            {"type": float, "min": 0.0,  "max": 100.0},
    "previous_gpa":          {"type": float, "min": 0.0,  "max": 4.0},
}


def _to_float(value, field_name: str) -> Tuple[float | None, str | None]:
    """Try to coerce value to float; return (value, error_msg)."""
    try:
        return float(value), None
    except (TypeError, ValueError):
        return None, f"'{field_name}' must be a number, got: {repr(value)}"


def validate_predict_input(data: dict) -> Tuple[bool, dict, List[str]]:
    """
    Validate the /api/predict request body.

    Returns:
        (is_valid, cleaned_data, errors)
        - is_valid    : True if all fields pass validation
        - cleaned_data: Dict with coerced / normalised values
        - errors      : List of human-readable error strings
    """
    errors: List[str] = []
    cleaned: dict = {}

    if not isinstance(data, dict):
        return False, {}, ["Request body must be a JSON object."]

    # ── student_id ──────────────────────────────────────────────────────────
    student_id = data.get("student_id", "")
    if not student_id:
        errors.append("'student_id' is required.")
    elif not isinstance(student_id, str):
        errors.append("'student_id' must be a string.")
    elif not STUDENT_ID_RE.match(str(student_id).strip()):
        errors.append(
            "'student_id' must be 3–20 alphanumeric characters "
            "(letters, digits, underscore, hyphen)."
        )
    else:
        cleaned["student_id"] = str(student_id).strip().upper()

    # ── student_name ────────────────────────────────────────────────────────
    student_name = data.get("student_name", "")
    if not student_name:
        errors.append("'student_name' is required.")
    elif not isinstance(student_name, (str, int, float)):
        errors.append("'student_name' must be a string.")
    else:
        name = str(student_name).strip()
        if len(name) < 2 or len(name) > 100:
            errors.append("'student_name' must be between 2 and 100 characters.")
        else:
            cleaned["student_name"] = name

    # ── Numeric feature fields ───────────────────────────────────────────────
    for field, rule in FIELD_RULES.items():
        raw = data.get(field)
        if raw is None:
            errors.append(f"'{field}' is required.")
            continue

        val, err = _to_float(raw, field)
        if err:
            errors.append(err)
            continue

        if val < rule["min"] or val > rule["max"]:
            errors.append(
                f"'{field}' must be between {rule['min']} and {rule['max']}, got {val}."
            )
            continue

        cleaned[field] = round(val, 4)

    is_valid = len(errors) == 0
    return is_valid, cleaned, errors


def validate_student_id_query(student_id: str | None) -> Tuple[bool, str | None, List[str]]:
    """
    Validate the student_id query parameter for /api/history.

    Returns:
        (is_valid, cleaned_id, errors)
    """
    errors: List[str] = []
    if not student_id:
        errors.append("Query parameter 'student_id' is required.")
        return False, None, errors

    student_id = str(student_id).strip().upper()
    if not STUDENT_ID_RE.match(student_id):
        errors.append(
            "'student_id' must be 3–20 alphanumeric characters "
            "(letters, digits, underscore, hyphen)."
        )
        return False, None, errors

    return True, student_id, []
