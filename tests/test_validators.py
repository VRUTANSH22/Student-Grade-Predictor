"""
tests/test_validators.py — Unit Tests for Input Validation
============================================================
Run with: pytest tests/test_validators.py -v
"""

import pytest
from app.validators import validate_predict_input, validate_student_id_query

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def valid_payload():
    return {
        "student_id":            "STU001",
        "student_name":          "John Doe",
        "attendance_percentage": 85.5,
        "study_hours_per_week":  15.0,
        "assignment_score":      78.0,
        "quiz_marks":            82.0,
        "previous_gpa":          3.5,
    }


# ── validate_predict_input ────────────────────────────────────────────────────

class TestValidatePredictInput:

    def test_valid_payload_passes(self, valid_payload):
        ok, cleaned, errors = validate_predict_input(valid_payload)
        assert ok is True
        assert errors == []
        assert cleaned["student_id"] == "STU001"

    def test_student_id_uppercased(self, valid_payload):
        valid_payload["student_id"] = "stu001"
        _, cleaned, _ = validate_predict_input(valid_payload)
        assert cleaned["student_id"] == "STU001"

    def test_missing_student_id(self, valid_payload):
        del valid_payload["student_id"]
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is False
        assert any("student_id" in e for e in errors)

    def test_student_id_too_short(self, valid_payload):
        valid_payload["student_id"] = "AB"  # only 2 chars
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is False

    def test_student_id_too_long(self, valid_payload):
        valid_payload["student_id"] = "A" * 21
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is False

    def test_student_id_special_chars_rejected(self, valid_payload):
        valid_payload["student_id"] = "STU@001"
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is False

    def test_student_id_hyphens_and_underscores_allowed(self, valid_payload):
        valid_payload["student_id"] = "STU_001-A"
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is True

    def test_missing_student_name(self, valid_payload):
        del valid_payload["student_name"]
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is False

    def test_attendance_out_of_range_high(self, valid_payload):
        valid_payload["attendance_percentage"] = 101
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is False
        assert any("attendance" in e for e in errors)

    def test_attendance_out_of_range_low(self, valid_payload):
        valid_payload["attendance_percentage"] = -1
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is False

    def test_attendance_boundary_zero(self, valid_payload):
        valid_payload["attendance_percentage"] = 0
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is True

    def test_attendance_boundary_hundred(self, valid_payload):
        valid_payload["attendance_percentage"] = 100
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is True

    def test_study_hours_max(self, valid_payload):
        valid_payload["study_hours_per_week"] = 168
        ok, _, _ = validate_predict_input(valid_payload)
        assert ok is True

    def test_study_hours_over_max(self, valid_payload):
        valid_payload["study_hours_per_week"] = 169
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is False

    def test_gpa_boundary_zero(self, valid_payload):
        valid_payload["previous_gpa"] = 0.0
        ok, _, _ = validate_predict_input(valid_payload)
        assert ok is True

    def test_gpa_boundary_four(self, valid_payload):
        valid_payload["previous_gpa"] = 4.0
        ok, _, _ = validate_predict_input(valid_payload)
        assert ok is True

    def test_gpa_over_four(self, valid_payload):
        valid_payload["previous_gpa"] = 4.1
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is False

    def test_string_numbers_coerced(self, valid_payload):
        valid_payload["attendance_percentage"] = "85.5"
        ok, cleaned, _ = validate_predict_input(valid_payload)
        assert ok is True
        assert isinstance(cleaned["attendance_percentage"], float)

    def test_non_numeric_field_rejected(self, valid_payload):
        valid_payload["attendance_percentage"] = "eighty"
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is False

    def test_missing_numeric_field(self, valid_payload):
        del valid_payload["quiz_marks"]
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is False
        assert any("quiz_marks" in e for e in errors)

    def test_non_dict_input_rejected(self):
        ok, _, errors = validate_predict_input("not a dict")
        assert ok is False

    def test_multiple_errors_returned(self, valid_payload):
        valid_payload["attendance_percentage"] = 999
        valid_payload["previous_gpa"]          = 5.0
        del valid_payload["student_name"]
        ok, _, errors = validate_predict_input(valid_payload)
        assert ok is False
        assert len(errors) >= 2


# ── validate_student_id_query ─────────────────────────────────────────────────

class TestValidateStudentIdQuery:

    def test_valid_id(self):
        ok, cleaned, errors = validate_student_id_query("STU001")
        assert ok is True
        assert cleaned == "STU001"
        assert errors == []

    def test_lowercase_uppercased(self):
        ok, cleaned, _ = validate_student_id_query("stu001")
        assert ok is True
        assert cleaned == "STU001"

    def test_none_rejected(self):
        ok, _, errors = validate_student_id_query(None)
        assert ok is False
        assert errors

    def test_empty_string_rejected(self):
        ok, _, errors = validate_student_id_query("")
        assert ok is False

    def test_too_short_rejected(self):
        ok, _, errors = validate_student_id_query("AB")
        assert ok is False

    def test_special_chars_rejected(self):
        ok, _, errors = validate_student_id_query("STU#001")
        assert ok is False
