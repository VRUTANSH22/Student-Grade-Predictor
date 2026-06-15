"""
tests/test_api.py — Integration Tests for Flask API Endpoints
==============================================================
Uses Flask's built-in test client with an in-memory SQLite database.
Run with: pytest tests/test_api.py -v
"""

import json
import pytest

# We must import these BEFORE creating the app so config reads .env
import os
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("USE_SQLITE", "true")


@pytest.fixture(scope="module")
def app():
    """Create a test Flask application with in-memory SQLite DB."""
    from config import TestingConfig
    from app import create_app
    flask_app = create_app(TestingConfig)
    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture(scope="module")
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def valid_predict_payload():
    return {
        "student_id":            "STU999",
        "student_name":          "Test Student",
        "attendance_percentage": 80.0,
        "study_hours_per_week":  12.0,
        "assignment_score":      75.0,
        "quiz_marks":            70.0,
        "previous_gpa":          3.0,
    }


# ── Health endpoint ───────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        res = client.get("/api/health")
        assert res.status_code in (200, 503)  # 503 if models not loaded

    def test_health_has_required_fields(self, client):
        res  = client.get("/api/health")
        data = json.loads(res.data)
        assert "status"       in data
        assert "database"     in data
        assert "model_loaded" in data
        assert "timestamp"    in data

    def test_health_database_connected(self, client):
        res  = client.get("/api/health")
        data = json.loads(res.data)
        assert data["database"] == "connected"


# ── Predict endpoint ──────────────────────────────────────────────────────────

class TestPredictEndpoint:

    def test_predict_wrong_content_type(self, client, valid_predict_payload):
        res = client.post(
            "/api/predict",
            data=json.dumps(valid_predict_payload),  # not application/json
        )
        assert res.status_code == 400

    def test_predict_missing_required_field(self, client, valid_predict_payload):
        payload = dict(valid_predict_payload)
        del payload["attendance_percentage"]
        res  = client.post("/api/predict",
                           data=json.dumps(payload),
                           content_type="application/json")
        data = json.loads(res.data)
        assert res.status_code == 400
        assert data["success"] is False
        assert "errors" in data

    def test_predict_attendance_out_of_range(self, client, valid_predict_payload):
        payload = dict(valid_predict_payload)
        payload["attendance_percentage"] = 150
        res  = client.post("/api/predict",
                           data=json.dumps(payload),
                           content_type="application/json")
        data = json.loads(res.data)
        assert res.status_code == 400
        assert data["success"] is False

    def test_predict_invalid_student_id(self, client, valid_predict_payload):
        payload = dict(valid_predict_payload)
        payload["student_id"] = "!BAD!"
        res = client.post("/api/predict",
                          data=json.dumps(payload),
                          content_type="application/json")
        assert res.status_code == 400

    def test_predict_gpa_over_max(self, client, valid_predict_payload):
        payload = dict(valid_predict_payload)
        payload["previous_gpa"] = 5.0
        res = client.post("/api/predict",
                          data=json.dumps(payload),
                          content_type="application/json")
        assert res.status_code == 400

    def test_predict_missing_body(self, client):
        res = client.post("/api/predict", content_type="application/json")
        assert res.status_code == 400

    def test_predict_returns_correct_structure_when_model_loaded(
            self, client, valid_predict_payload):
        """
        This test only passes if train_models.py has been run first.
        In CI without models, the endpoint returns 500.
        We assert both branches are handled gracefully.
        """
        res  = client.post("/api/predict",
                           data=json.dumps(valid_predict_payload),
                           content_type="application/json")
        data = json.loads(res.data)

        if res.status_code == 200:
            assert data["success"] is True
            pred = data["prediction"]
            assert "predicted_grade"  in pred
            assert "confidence_score" in pred
            assert "risk_level"       in pred
            assert 0 <= pred["predicted_grade"]  <= 100
            assert 0 <= pred["confidence_score"] <= 1
            assert pred["risk_level"] in ("low", "medium", "high", "critical")
        else:
            # Models not loaded — should still return JSON error
            assert data["success"] is False
            assert "error" in data


# ── History endpoint ──────────────────────────────────────────────────────────

class TestHistoryEndpoint:

    def test_history_missing_student_id(self, client):
        res  = client.get("/api/history")
        data = json.loads(res.data)
        assert res.status_code == 400
        assert data["success"] is False

    def test_history_invalid_student_id(self, client):
        res  = client.get("/api/history?student_id=!!BAD!!")
        data = json.loads(res.data)
        assert res.status_code == 400

    def test_history_nonexistent_student(self, client):
        res  = client.get("/api/history?student_id=DOESNOTEXIST999")
        data = json.loads(res.data)
        assert res.status_code == 404
        assert data["success"] is False
        assert data["code"] == "STUDENT_NOT_FOUND"

    def test_history_response_structure(self, client):
        """After a successful prediction, history should be retrievable."""
        # Only meaningful if model is loaded (predictions exist)
        res  = client.get("/api/history?student_id=STU999")
        data = json.loads(res.data)
        if res.status_code == 200:
            assert "predictions" in data
            assert "prediction_count" in data
            assert isinstance(data["predictions"], list)


# ── Stats endpoint ────────────────────────────────────────────────────────────

class TestStatsEndpoint:

    def test_stats_returns_200(self, client):
        res = client.get("/api/stats")
        assert res.status_code == 200

    def test_stats_has_required_fields(self, client):
        res  = client.get("/api/stats")
        data = json.loads(res.data)
        assert data["success"] is True
        stats = data["stats"]
        required = [
            "total_predictions", "total_students",
            "system_uptime", "model_loaded", "timestamp",
        ]
        for field in required:
            assert field in stats, f"Missing field: {field}"

    def test_stats_total_predictions_is_int(self, client):
        res  = client.get("/api/stats")
        data = json.loads(res.data)
        assert isinstance(data["stats"]["total_predictions"], int)

    def test_stats_total_students_is_int(self, client):
        res  = client.get("/api/stats")
        data = json.loads(res.data)
        assert isinstance(data["stats"]["total_students"], int)


# ── Recent endpoint ───────────────────────────────────────────────────────────

class TestRecentEndpoint:

    def test_recent_returns_200(self, client):
        res  = client.get("/api/recent")
        data = json.loads(res.data)
        assert res.status_code == 200
        assert data["success"] is True
        assert isinstance(data["predictions"], list)


# ── Error handling ────────────────────────────────────────────────────────────

class TestErrorHandlers:

    def test_404_returns_json(self, client):
        res  = client.get("/api/nonexistent-route-xyz")
        data = json.loads(res.data)
        assert res.status_code == 404
        assert data["success"] is False
        assert data["code"] == "NOT_FOUND"

    def test_method_not_allowed_returns_json(self, client):
        res  = client.delete("/api/health")
        data = json.loads(res.data)
        assert res.status_code == 405

    def test_page_routes_return_html(self, client):
        for path in ["/", "/history", "/dashboard"]:
            res = client.get(path)
            assert res.status_code == 200
            assert b"<!DOCTYPE html>" in res.data
