"""
app/models.py — ML Model Manager
==================================
Singleton that loads the pre-trained Random Forest, XGBoost, and StandardScaler
from disk once at startup and exposes a unified predict() interface.

Confidence score:
    Uses the standard deviation of predictions across all RF estimator trees.
    A low std → high confidence; a high std → low confidence.
    Mapped to a [0, 1] range using a sigmoid-like inversion.

Risk level:
    predicted_grade < 50   → "critical"
    50 ≤ grade < 60        → "high"
    60 ≤ grade < 75        → "medium"
    grade ≥ 75             → "low"
"""

import os
import json
import logging
import numpy as np
import joblib

logger = logging.getLogger(__name__)

# ── Feature column order (must match training) ─────────────────────────────────
FEATURE_COLUMNS = [
    "attendance_percentage",
    "study_hours_per_week",
    "assignment_score",
    "quiz_marks",
    "previous_gpa",
]

# Risk thresholds
RISK_THRESHOLDS = {
    "critical": 50,
    "high":     60,
    "medium":   75,
}


def _compute_risk_level(grade: float) -> str:
    if grade < RISK_THRESHOLDS["critical"]:
        return "critical"
    if grade < RISK_THRESHOLDS["high"]:
        return "high"
    if grade < RISK_THRESHOLDS["medium"]:
        return "medium"
    return "low"


def _rf_confidence(rf_model, X_scaled: np.ndarray) -> float:
    """
    Compute confidence score from RF tree diversity.
    std across individual tree predictions → mapped to [0, 1].
    High std = low confidence; low std = high confidence.
    """
    tree_preds = np.array([t.predict(X_scaled) for t in rf_model.estimators_])
    std = float(np.std(tree_preds))
    # Sigmoid-like inversion: std=0 → confidence≈1.0, std=10 → confidence≈0.5
    confidence = 1.0 / (1.0 + std / 10.0)
    return round(min(max(confidence, 0.0), 1.0), 3)


class ModelManager:
    """Singleton class that owns the ML models and exposes predict()."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._rf_model  = None
        self._xgb_model = None
        self._scaler    = None
        self._meta      = {}
        self._loaded    = False
        self._model_dir = None
        self._initialized = True

    def load(self, model_dir: str, rf_weight: float = 0.6, xgb_weight: float = 0.4):
        """
        Load models and scaler from disk.
        Raises FileNotFoundError if any artefact is missing.
        """
        self._model_dir  = model_dir
        self._rf_weight  = rf_weight
        self._xgb_weight = xgb_weight

        rf_path  = os.path.join(model_dir, "random_forest_model.pkl")
        xgb_path = os.path.join(model_dir, "xgboost_model.pkl")
        sc_path  = os.path.join(model_dir, "scaler.pkl")
        meta_path = os.path.join(model_dir, "model_metadata.json")

        missing = [p for p in [rf_path, xgb_path, sc_path] if not os.path.exists(p)]
        if missing:
            raise FileNotFoundError(
                f"Model files not found: {missing}\n"
                f"Run `python train_models.py` first."
            )

        self._rf_model  = joblib.load(rf_path)
        self._xgb_model = joblib.load(xgb_path)
        self._scaler    = joblib.load(sc_path)
        self._loaded    = True

        if os.path.exists(meta_path):
            with open(meta_path) as f:
                self._meta = json.load(f)

        logger.info(
            "ModelManager: loaded RF + XGBoost + Scaler from '%s'",
            model_dir,
        )

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def predict(self, features: dict) -> dict:
        """
        Make an ensemble prediction.

        Args:
            features: dict with keys from FEATURE_COLUMNS

        Returns:
            dict with keys:
                predicted_grade (float 0–100)
                confidence_score (float 0–1)
                risk_level (str)
                rf_prediction (float)
                xgb_prediction (float)
        """
        if not self._loaded:
            raise RuntimeError("Models not loaded. Call ModelManager.load() first.")

        # Build input array in correct column order
        row = np.array([[features[col] for col in FEATURE_COLUMNS]], dtype=np.float64)
        X_scaled = self._scaler.transform(row)

        rf_pred  = float(self._rf_model.predict(X_scaled)[0])
        xgb_pred = float(self._xgb_model.predict(X_scaled)[0])

        # Weighted ensemble
        ensemble_grade = (
            self._rf_weight  * rf_pred +
            self._xgb_weight * xgb_pred
        )
        ensemble_grade = round(float(np.clip(ensemble_grade, 0, 100)), 2)

        confidence = _rf_confidence(self._rf_model, X_scaled)
        risk_level = _compute_risk_level(ensemble_grade)

        return {
            "predicted_grade":  ensemble_grade,
            "confidence_score": confidence,
            "risk_level":       risk_level,
            "rf_prediction":    round(rf_pred,  2),
            "xgb_prediction":   round(xgb_pred, 2),
        }


# ── Module-level singleton instance ───────────────────────────────────────────
model_manager = ModelManager()
