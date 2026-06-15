"""
tests/test_models.py — Unit Tests for ModelManager
===================================================
Tests the prediction logic in isolation.
If trained models exist in /models/, tests run against real models.
If not, models are mocked to allow CI to run without training first.
Run with: pytest tests/test_models.py -v
"""

import os
import pytest
import numpy as np
from unittest.mock import MagicMock, patch


# ── Helpers ────────────────────────────────────────────────────────────────────

SAMPLE_FEATURES = {
    "attendance_percentage": 85.0,
    "study_hours_per_week":  15.0,
    "assignment_score":      78.0,
    "quiz_marks":            82.0,
    "previous_gpa":          3.5,
}

MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "models"
)
MODELS_EXIST = all(
    os.path.exists(os.path.join(MODELS_DIR, f))
    for f in ["random_forest_model.pkl", "xgboost_model.pkl", "scaler.pkl"]
)


# ── Tests with real models (skipped if not trained yet) ──────────────────────

@pytest.mark.skipif(not MODELS_EXIST, reason="Models not trained — run train_models.py first")
class TestModelManagerReal:

    @pytest.fixture(autouse=True)
    def load_models(self):
        from app.models import ModelManager
        # Reset singleton for clean test
        ModelManager._instance = None
        from app.models import model_manager
        model_manager.load(MODELS_DIR)
        yield model_manager
        ModelManager._instance = None

    def test_predict_returns_dict(self, load_models):
        result = load_models.predict(SAMPLE_FEATURES)
        assert isinstance(result, dict)

    def test_predict_grade_in_range(self, load_models):
        result = load_models.predict(SAMPLE_FEATURES)
        assert 0 <= result["predicted_grade"] <= 100

    def test_predict_confidence_in_range(self, load_models):
        result = load_models.predict(SAMPLE_FEATURES)
        assert 0.0 <= result["confidence_score"] <= 1.0

    def test_predict_risk_level_valid(self, load_models):
        result = load_models.predict(SAMPLE_FEATURES)
        assert result["risk_level"] in ("low", "medium", "high", "critical")

    def test_predict_contains_all_keys(self, load_models):
        result = load_models.predict(SAMPLE_FEATURES)
        for key in ("predicted_grade", "confidence_score", "risk_level",
                    "rf_prediction", "xgb_prediction"):
            assert key in result, f"Missing key: {key}"

    def test_low_attendance_gives_lower_grade(self, load_models):
        low = dict(SAMPLE_FEATURES, attendance_percentage=30, study_hours_per_week=2,
                   assignment_score=30, quiz_marks=30, previous_gpa=1.0)
        high = SAMPLE_FEATURES
        result_low  = load_models.predict(low)
        result_high = load_models.predict(high)
        assert result_low["predicted_grade"] < result_high["predicted_grade"]

    def test_rf_and_xgb_predictions_are_close(self, load_models):
        result = load_models.predict(SAMPLE_FEATURES)
        diff = abs(result["rf_prediction"] - result["xgb_prediction"])
        assert diff < 25, f"RF and XGB predictions differ too much: {diff}"

    def test_is_loaded_true_after_load(self, load_models):
        assert load_models.is_loaded is True


# ── Tests with mocked models (always run) ─────────────────────────────────────

class TestModelManagerMocked:

    @pytest.fixture
    def manager_with_mocks(self):
        """Create a ModelManager with mocked RF, XGBoost, and Scaler."""
        from app.models import ModelManager
        ModelManager._instance = None
        from app.models import model_manager as mm

        mock_rf  = MagicMock()
        mock_xgb = MagicMock()
        mock_sc  = MagicMock()

        mock_rf.predict.return_value  = np.array([78.5])
        mock_xgb.predict.return_value = np.array([80.0])
        mock_sc.transform.return_value = np.array([[0.1, 0.2, 0.3, 0.4, 0.5]])

        # Mock individual tree estimators for confidence calculation
        tree_mock = MagicMock()
        tree_mock.predict.return_value = np.array([78.0])
        mock_rf.estimators_ = [tree_mock] * 10

        mm._rf_model  = mock_rf
        mm._xgb_model = mock_xgb
        mm._scaler    = mock_sc
        mm._loaded    = True
        mm._rf_weight  = 0.6
        mm._xgb_weight = 0.4

        yield mm

        # Cleanup
        ModelManager._instance = None

    def test_mocked_predict_returns_dict(self, manager_with_mocks):
        result = manager_with_mocks.predict(SAMPLE_FEATURES)
        assert isinstance(result, dict)

    def test_mocked_grade_in_range(self, manager_with_mocks):
        result = manager_with_mocks.predict(SAMPLE_FEATURES)
        assert 0 <= result["predicted_grade"] <= 100

    def test_mocked_ensemble_weighted_average(self, manager_with_mocks):
        """Verify weighted average: 0.6*78.5 + 0.4*80.0 = 47.1 + 32.0 = 79.1"""
        result = manager_with_mocks.predict(SAMPLE_FEATURES)
        expected = round(0.6 * 78.5 + 0.4 * 80.0, 2)
        assert abs(result["predicted_grade"] - expected) < 0.1

    def test_mocked_confidence_returned(self, manager_with_mocks):
        result = manager_with_mocks.predict(SAMPLE_FEATURES)
        assert 0 <= result["confidence_score"] <= 1

    def test_not_loaded_raises_runtime_error(self):
        from app.models import ModelManager
        ModelManager._instance = None
        from app.models import model_manager as mm
        mm._loaded = False
        with pytest.raises(RuntimeError, match="not loaded"):
            mm.predict(SAMPLE_FEATURES)
        ModelManager._instance = None

    def test_risk_level_critical_for_low_grade(self, manager_with_mocks):
        manager_with_mocks._rf_model.predict.return_value  = np.array([30.0])
        manager_with_mocks._xgb_model.predict.return_value = np.array([30.0])
        for t in manager_with_mocks._rf_model.estimators_:
            t.predict.return_value = np.array([30.0])
        result = manager_with_mocks.predict(SAMPLE_FEATURES)
        assert result["risk_level"] == "critical"

    def test_risk_level_low_for_high_grade(self, manager_with_mocks):
        manager_with_mocks._rf_model.predict.return_value  = np.array([90.0])
        manager_with_mocks._xgb_model.predict.return_value = np.array([90.0])
        for t in manager_with_mocks._rf_model.estimators_:
            t.predict.return_value = np.array([90.0])
        result = manager_with_mocks.predict(SAMPLE_FEATURES)
        assert result["risk_level"] == "low"
