"""
train_models.py — Standalone ML Model Training Script
======================================================
Generates a synthetic-but-realistic student dataset, trains Random Forest
and XGBoost regressors (with GridSearchCV), evaluates them, and saves the
fitted models + scaler to the /models/ directory.

Usage:
    python train_models.py

Outputs (in models/):
    random_forest_model.pkl
    xgboost_model.pkl
    scaler.pkl
    training_report.txt
"""

import os
import json
import sys
import numpy as np
import pandas as pd
import joblib
from datetime import datetime

# Force UTF-8 output so box-drawing chars work on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_score
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from xgboost import XGBRegressor

# ── Seed for reproducibility ──────────────────────────────────────────────────
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

N_SAMPLES = 2500  # number of synthetic students


# ── 1. Generate Synthetic Dataset ─────────────────────────────────────────────

def generate_dataset(n: int) -> pd.DataFrame:
    """
    Generates n rows of synthetic student data with realistic correlations.

    Features:
        attendance_percentage  : 40 – 100  (Beta-distributed, skewed high)
        study_hours_per_week   : 2  – 40   (Gamma-distributed)
        assignment_score       : 30 – 100  (Normal, correlated with study hrs)
        quiz_marks             : 20 – 100  (Normal, correlated with attendance)
        previous_gpa           : 1.0 – 4.0 (Beta-distributed)

    Target:
        final_grade            : 0 – 100   (weighted combination + noise)
    """
    attendance = np.clip(np.random.beta(6, 2, n) * 100, 40, 100)
    study_hours = np.clip(np.random.gamma(3, 4, n), 2, 40)
    previous_gpa = np.clip(np.random.beta(4, 2, n) * 4.0, 1.0, 4.0)

    # assignment_score correlated with study hours
    assignment_base = study_hours * 1.5 + previous_gpa * 8
    assignment_score = np.clip(
        assignment_base + np.random.normal(0, 8, n), 30, 100
    )

    # quiz_marks correlated with attendance
    quiz_base = attendance * 0.6 + previous_gpa * 7
    quiz_marks = np.clip(
        quiz_base + np.random.normal(0, 7, n), 20, 100
    )

    # Final grade: weighted combination of all features + small noise
    final_grade = (
        0.25 * attendance
        + 0.20 * (study_hours / 40 * 100)
        + 0.20 * assignment_score
        + 0.20 * quiz_marks
        + 0.15 * (previous_gpa / 4.0 * 100)
        + np.random.normal(0, 5, n)
    )
    final_grade = np.clip(final_grade, 0, 100)

    df = pd.DataFrame({
        "attendance_percentage": np.round(attendance, 2),
        "study_hours_per_week":  np.round(study_hours, 2),
        "assignment_score":      np.round(assignment_score, 2),
        "quiz_marks":            np.round(quiz_marks, 2),
        "previous_gpa":          np.round(previous_gpa, 2),
        "final_grade":           np.round(final_grade, 2),
    })
    return df


# ── 2. Train & Evaluate Helper ────────────────────────────────────────────────

def evaluate_model(name: str, model, X_test: np.ndarray, y_test: np.ndarray) -> dict:
    y_pred = model.predict(X_test)
    r2   = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae  = mean_absolute_error(y_test, y_pred)
    print(f"\n{'-'*50}")
    print(f"  {name}")
    print(f"  R2   = {r2:.4f}")
    print(f"  RMSE = {rmse:.4f}")
    print(f"  MAE  = {mae:.4f}")
    return {"model": name, "r2": r2, "rmse": rmse, "mae": mae}


# ── 3. Main ───────────────────────────────────────────────────────────────────

def main():
    os.makedirs("models", exist_ok=True)

    print("=" * 50)
    print("  Student Performance Predictor -- Model Training")
    print("=" * 50)

    # Generate data
    print(f"\n[1/5] Generating {N_SAMPLES} synthetic student records...")
    df = generate_dataset(N_SAMPLES)

    FEATURE_COLS = [
        "attendance_percentage",
        "study_hours_per_week",
        "assignment_score",
        "quiz_marks",
        "previous_gpa",
    ]
    TARGET_COL = "final_grade"

    X = df[FEATURE_COLS].values
    y = df[TARGET_COL].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_SEED
    )

    # ── Scale
    print("[2/5] Fitting StandardScaler...")
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc  = scaler.transform(X_test)

    results = []

    # ── Random Forest
    print("[3/5] Training Random Forest (GridSearchCV)...")
    rf_params = {
        "n_estimators":      [100, 200],
        "max_depth":         [None, 10, 20],
        "min_samples_split": [2, 5],
        "min_samples_leaf":  [1, 2],
    }
    rf_base = RandomForestRegressor(random_state=RANDOM_SEED, n_jobs=-1)
    rf_gs   = GridSearchCV(rf_base, rf_params, cv=5, scoring="r2",
                           n_jobs=-1, verbose=0)
    rf_gs.fit(X_train_sc, y_train)
    best_rf = rf_gs.best_estimator_
    print(f"   Best RF params: {rf_gs.best_params_}")
    results.append(evaluate_model("Random Forest", best_rf, X_test_sc, y_test))

    # ── XGBoost
    print("[4/5] Training XGBoost (GridSearchCV)...")
    xgb_params = {
        "n_estimators":  [100, 200],
        "max_depth":     [4, 6, 8],
        "learning_rate": [0.05, 0.1],
        "subsample":     [0.8, 1.0],
    }
    xgb_base = XGBRegressor(
        random_state=RANDOM_SEED,
        objective="reg:squarederror",
        n_jobs=-1,
        verbosity=0,
    )
    xgb_gs = GridSearchCV(xgb_base, xgb_params, cv=5, scoring="r2",
                          n_jobs=-1, verbose=0)
    xgb_gs.fit(X_train_sc, y_train)
    best_xgb = xgb_gs.best_estimator_
    print(f"   Best XGB params: {xgb_gs.best_params_}")
    results.append(evaluate_model("XGBoost", best_xgb, X_test_sc, y_test))

    # ── Ensemble (weighted average)
    rf_w, xgb_w = 0.6, 0.4
    y_ens = rf_w * best_rf.predict(X_test_sc) + xgb_w * best_xgb.predict(X_test_sc)
    ens_r2   = r2_score(y_test, y_ens)
    ens_rmse = np.sqrt(mean_squared_error(y_test, y_ens))
    ens_mae  = mean_absolute_error(y_test, y_ens)
    print(f"\n  Ensemble (RF {rf_w:.0%} + XGB {xgb_w:.0%})")
    print(f"  R2   = {ens_r2:.4f}")
    print(f"  RMSE = {ens_rmse:.4f}")
    print(f"  MAE  = {ens_mae:.4f}")
    results.append({"model": "Ensemble", "r2": ens_r2, "rmse": ens_rmse, "mae": ens_mae})

    # ── Save artefacts
    print("\n[5/5] Saving models and scaler...")
    joblib.dump(best_rf,  "models/random_forest_model.pkl")
    joblib.dump(best_xgb, "models/xgboost_model.pkl")
    joblib.dump(scaler,   "models/scaler.pkl")

    # Save feature column order (critical for inference)
    meta = {
        "feature_columns": FEATURE_COLS,
        "target_column":   TARGET_COL,
        "n_training_samples": len(X_train),
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "results": results,
    }
    with open("models/model_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    # Save human-readable report
    report_lines = [
        "=" * 50,
        "  Training Report",
        f"  Generated: {datetime.utcnow().isoformat()}Z",
        "=" * 50,
    ]
    for r in results:
        report_lines += [
            f"\n  Model : {r['model']}",
            f"  R2    : {r['r2']:.4f}",
            f"  RMSE  : {r['rmse']:.4f}",
            f"  MAE   : {r['mae']:.4f}",
        ]
    report_lines.append("\n  Saved: models/random_forest_model.pkl")
    report_lines.append("  Saved: models/xgboost_model.pkl")
    report_lines.append("  Saved: models/scaler.pkl")
    report_lines.append("  Saved: models/model_metadata.json")

    with open("models/training_report.txt", "w") as f:
        f.write("\n".join(report_lines))

    print("\n" + "\n".join(report_lines))
    print("\nDone! Training complete.\n")


if __name__ == "__main__":
    main()
