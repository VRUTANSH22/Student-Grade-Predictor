"""
app/routes.py — All API & Page Routes
========================================
Defines a single Flask Blueprint that registers:

  Page routes (render HTML templates):
    GET  /                  → index.html   (prediction form)
    GET  /history           → history.html (prediction history browser)
    GET  /dashboard         → dashboard.html (system stats)

  API routes (JSON):
    POST /api/predict       → run ML prediction, store in DB, log entry
    GET  /api/history       → fetch prediction history for a student
    GET  /api/stats         → aggregate system statistics
    GET  /api/health        → health/liveness check

Flasgger YAML docstrings power the auto-generated Swagger UI at /apidocs.
"""

import time
import logging
import datetime

from flask import Blueprint, request, render_template, current_app
from sqlalchemy import text as sa_text

from app.validators    import validate_predict_input, validate_student_id_query
from app.models        import model_manager
from app.database      import (
    get_db_session, upsert_student, save_prediction,
    log_api_call, refresh_system_stats, Prediction, Student
)
from app.utils         import (
    success_response, error_response,
    utcnow_iso, get_uptime_str, get_remote_ip, get_db_size_mb
)

logger  = logging.getLogger(__name__)
bp      = Blueprint("main", __name__)


# ────────────────────────────────────────────────────────────────────────────────
#  Page routes
# ────────────────────────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/history")
def history_page():
    return render_template("history.html")


@bp.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


# ────────────────────────────────────────────────────────────────────────────────
#  POST /api/predict
# ────────────────────────────────────────────────────────────────────────────────

@bp.route("/api/predict", methods=["POST"])
def api_predict():
    """
    Run a student performance prediction.
    ---
    tags:
      - Predictions
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - student_id
            - student_name
            - attendance_percentage
            - study_hours_per_week
            - assignment_score
            - quiz_marks
            - previous_gpa
          properties:
            student_id:
              type: string
              example: STU001
            student_name:
              type: string
              example: John Doe
            attendance_percentage:
              type: number
              example: 85.5
            study_hours_per_week:
              type: number
              example: 15
            assignment_score:
              type: number
              example: 78
            quiz_marks:
              type: number
              example: 82
            previous_gpa:
              type: number
              example: 3.5
    responses:
      200:
        description: Prediction successful
      400:
        description: Validation error
      500:
        description: Server error
    """
    t_start    = time.time()
    remote_ip  = get_remote_ip()
    user_agent = request.headers.get("User-Agent", "unknown")

    # ── Parse JSON ──────────────────────────────────────────────────────────
    data = request.get_json(silent=True)
    if data is None:
        return error_response(
            "Request body must be valid JSON with Content-Type: application/json",
            code="INVALID_JSON",
            status_code=400,
        )

    # ── Validate ─────────────────────────────────────────────────────────────
    is_valid, cleaned, errors = validate_predict_input(data)
    if not is_valid:
        _log_api(
            endpoint="/api/predict", method="POST",
            student_id=data.get("student_id"),
            request_data=data, status=400,
            elapsed_ms=_ms(t_start),
            error="; ".join(errors),
            remote_ip=remote_ip, user_agent=user_agent,
        )
        return error_response(
            "Validation failed", code="VALIDATION_ERROR",
            status_code=400, errors=errors
        )

    student_id   = cleaned["student_id"]
    student_name = cleaned["student_name"]

    # ── ML Prediction ────────────────────────────────────────────────────────
    try:
        features = {
            "attendance_percentage": cleaned["attendance_percentage"],
            "study_hours_per_week":  cleaned["study_hours_per_week"],
            "assignment_score":      cleaned["assignment_score"],
            "quiz_marks":            cleaned["quiz_marks"],
            "previous_gpa":          cleaned["previous_gpa"],
        }
        result = model_manager.predict(features)
    except Exception as exc:
        logger.exception("Model prediction failed", extra={"student_id": student_id})
        _log_api(
            endpoint="/api/predict", method="POST",
            student_id=student_id, request_data=cleaned,
            status=500, elapsed_ms=_ms(t_start),
            error=str(exc), remote_ip=remote_ip, user_agent=user_agent,
        )
        return error_response(
            "Model prediction failed. Please try again.",
            code="MODEL_ERROR", status_code=500
        )

    # ── Persist to DB ────────────────────────────────────────────────────────
    prediction_ts = datetime.datetime.utcnow()
    try:
        with get_db_session() as session:
            upsert_student(session, student_id, student_name)
            pred_obj = save_prediction(session, {
                "student_id":            student_id,
                "predicted_grade":       result["predicted_grade"],
                "confidence_score":      result["confidence_score"],
                "attendance_percentage": cleaned["attendance_percentage"],
                "study_hours":           cleaned["study_hours_per_week"],
                "assignment_score":      cleaned["assignment_score"],
                "quiz_marks":            cleaned["quiz_marks"],
                "previous_gpa":          cleaned["previous_gpa"],
                "risk_level":            result["risk_level"],
                "model_used":            "rf+xgboost-ensemble",
            })
            session.flush()
            prediction_id = pred_obj.prediction_id
    except Exception as exc:
        logger.exception("DB write failed", extra={"student_id": student_id})
        # Non-fatal: return prediction even if DB write fails
        prediction_id = None

    elapsed = _ms(t_start)

    # ── Structured log ───────────────────────────────────────────────────────
    logger.info(
        "Prediction completed",
        extra={
            "endpoint":          "/api/predict",
            "method":            "POST",
            "student_id":        student_id,
            "input_features":    features,
            "prediction_result": {
                "predicted_grade": result["predicted_grade"],
                "confidence":      result["confidence_score"],
                "risk_level":      result["risk_level"],
            },
            "execution_time_ms": elapsed,
            "status":            "success",
            "response_code":     200,
            "error_message":     None,
            "user_agent":        user_agent,
            "remote_ip":         remote_ip,
        }
    )

    _log_api(
        endpoint="/api/predict", method="POST",
        student_id=student_id, request_data=cleaned,
        status=200, elapsed_ms=elapsed,
        error=None, remote_ip=remote_ip, user_agent=user_agent,
    )

    return success_response(
        data={
            "prediction": {
                "prediction_id":        prediction_id,
                "student_id":           student_id,
                "student_name":         student_name,
                "predicted_grade":      result["predicted_grade"],
                "confidence_score":     result["confidence_score"],
                "risk_level":           result["risk_level"],
                "rf_prediction":        result["rf_prediction"],
                "xgb_prediction":       result["xgb_prediction"],
                "prediction_timestamp": prediction_ts.isoformat() + "Z",
                "input_features":       features,
            }
        },
        message="Prediction successful",
    )


# ────────────────────────────────────────────────────────────────────────────────
#  GET /api/history
# ────────────────────────────────────────────────────────────────────────────────

@bp.route("/api/history", methods=["GET"])
def api_history():
    """
    Retrieve prediction history for a student.
    ---
    tags:
      - History
    parameters:
      - name: student_id
        in: query
        type: string
        required: true
        example: STU001
      - name: limit
        in: query
        type: integer
        required: false
        default: 50
    responses:
      200:
        description: Prediction history returned
      400:
        description: Validation error
      404:
        description: Student not found
    """
    student_id_raw = request.args.get("student_id")
    limit = min(int(request.args.get("limit", 50)), 200)

    is_valid, student_id, errors = validate_student_id_query(student_id_raw)
    if not is_valid:
        return error_response("Validation failed", code="VALIDATION_ERROR",
                              status_code=400, errors=errors)

    try:
        with get_db_session() as session:
            student = session.get(Student, student_id)
            if student is None:
                return error_response(
                    f"No records found for student_id '{student_id}'",
                    code="STUDENT_NOT_FOUND", status_code=404
                )

            preds = (
                session.query(Prediction)
                .filter(Prediction.student_id == student_id)
                .order_by(Prediction.prediction_timestamp.desc())
                .limit(limit)
                .all()
            )

            return success_response(
                data={
                    "student_id":       student_id,
                    "student_name":     student.student_name,
                    "prediction_count": len(preds),
                    "predictions":      [p.to_dict() for p in preds],
                },
                message="History retrieved successfully",
            )
    except Exception as exc:
        logger.exception("History fetch failed", extra={"student_id": student_id})
        return error_response("Failed to fetch history.", code="DB_ERROR",
                              status_code=500)


# ────────────────────────────────────────────────────────────────────────────────
#  GET /api/stats
# ────────────────────────────────────────────────────────────────────────────────

@bp.route("/api/stats", methods=["GET"])
def api_stats():
    """
    Retrieve aggregate system statistics.
    ---
    tags:
      - Monitoring
    responses:
      200:
        description: Statistics returned
    """
    try:
        with get_db_session() as session:
            stats = refresh_system_stats(session)

        # Last prediction timestamp
        last_pred = None
        with get_db_session() as session:
            last = (
                session.query(Prediction.prediction_timestamp)
                .order_by(Prediction.prediction_timestamp.desc())
                .first()
            )
            if last:
                last_pred = last[0].isoformat() + "Z"

        db_uri  = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
        db_size = get_db_size_mb(db_uri)

        return success_response(
            data={
                "stats": {
                    "total_predictions":   stats["total_predictions"],
                    "total_students":      stats["total_students"],
                    "avg_predicted_grade": stats["avg_predicted_grade"],
                    "system_uptime":       get_uptime_str(),
                    "database_size_mb":    db_size,
                    "last_prediction":     last_pred,
                    "model_loaded":        model_manager.is_loaded,
                    "timestamp":           utcnow_iso(),
                }
            },
            message="Stats retrieved successfully",
        )
    except Exception as exc:
        logger.exception("Stats query failed")
        return error_response("Failed to retrieve stats.", code="DB_ERROR",
                              status_code=500)


# ────────────────────────────────────────────────────────────────────────────────
#  GET /api/health
# ────────────────────────────────────────────────────────────────────────────────

@bp.route("/api/health", methods=["GET"])
def api_health():
    """
    Liveness / health check endpoint.
    ---
    tags:
      - Monitoring
    responses:
      200:
        description: Service is healthy
      503:
        description: Service is degraded
    """
    db_ok    = True
    db_error = None
    try:
        with get_db_session() as session:
            session.execute(sa_text("SELECT 1"))
    except Exception as exc:
        db_ok    = False
        db_error = str(exc)

    model_ok = model_manager.is_loaded
    healthy  = db_ok and model_ok

    payload = {
        "status":        "healthy" if healthy else "degraded",
        "database":      "connected" if db_ok else f"error: {db_error}",
        "model_loaded":  model_ok,
        "uptime":        get_uptime_str(),
        "timestamp":     utcnow_iso(),
    }

    from flask import jsonify
    return jsonify(payload), (200 if healthy else 503)


# ────────────────────────────────────────────────────────────────────────────────
#  GET /api/recent  (used by dashboard auto-refresh)
# ────────────────────────────────────────────────────────────────────────────────

@bp.route("/api/recent", methods=["GET"])
def api_recent():
    """Return the 10 most recent predictions across all students."""
    limit = min(int(request.args.get("limit", 10)), 50)
    try:
        with get_db_session() as session:
            preds = (
                session.query(Prediction)
                .order_by(Prediction.prediction_timestamp.desc())
                .limit(limit)
                .all()
            )
            return success_response(
                data={"predictions": [p.to_dict() for p in preds]},
                message="Recent predictions retrieved",
            )
    except Exception as exc:
        logger.exception("Recent predictions fetch failed")
        return error_response("Failed to fetch recent predictions.",
                              code="DB_ERROR", status_code=500)


# ────────────────────────────────────────────────────────────────────────────────
#  Error handlers (registered on the app, not the blueprint)
# ────────────────────────────────────────────────────────────────────────────────

def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return error_response("The requested endpoint does not exist.",
                              code="NOT_FOUND", status_code=404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return error_response("HTTP method not allowed for this endpoint.",
                              code="METHOD_NOT_ALLOWED", status_code=405)

    @app.errorhandler(500)
    def internal_error(e):
        logger.error("Unhandled 500 error: %s", str(e))
        return error_response("An internal server error occurred.",
                              code="INTERNAL_ERROR", status_code=500)


# ── Internal helper ────────────────────────────────────────────────────────────

def _ms(t_start: float) -> int:
    return int((time.time() - t_start) * 1000)


def _log_api(endpoint, method, student_id, request_data,
             status, elapsed_ms, error, remote_ip, user_agent):
    """Fire-and-forget API log write (silently ignores DB errors)."""
    try:
        with get_db_session() as session:
            log_api_call(
                session        = session,
                endpoint       = endpoint,
                method         = method,
                student_id     = student_id,
                request_data   = request_data,
                response_status = status,
                execution_time_ms = elapsed_ms,
                error_message  = error,
                remote_ip      = remote_ip,
                user_agent     = user_agent,
            )
    except Exception:
        pass  # logging failure must never crash the main response
