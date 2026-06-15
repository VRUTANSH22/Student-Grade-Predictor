# API Documentation — Student Performance Predictor

**Base URL:** `http://localhost:5000`  
**Content-Type:** `application/json`  
**Interactive Docs:** `http://localhost:5000/apidocs` (Swagger UI)

---

## Standard Response Format

### Success
```json
{
  "success": true,
  "message": "...",
  "timestamp": "2026-06-12T10:30:45Z",
  "...": "endpoint-specific data"
}
```

### Error
```json
{
  "success": false,
  "error":   "Human-readable message",
  "code":    "ERROR_CODE",
  "timestamp": "2026-06-12T10:30:45Z",
  "errors": ["optional list of validation errors"]
}
```

### HTTP Status Codes
| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request / validation error |
| 404 | Resource not found |
| 405 | Method not allowed |
| 500 | Internal server error |
| 503 | Service degraded (health check) |

---

## Endpoints

### POST `/api/predict`
Run a student grade prediction using the RF + XGBoost ensemble.

**Request Body**
```json
{
  "student_id":            "STU001",
  "student_name":          "John Doe",
  "attendance_percentage": 85.5,
  "study_hours_per_week":  15,
  "assignment_score":      78,
  "quiz_marks":            82,
  "previous_gpa":          3.5
}
```

**Field Validation Rules**

| Field | Type | Range | Required |
|-------|------|-------|----------|
| `student_id` | string | 3–20 alphanumeric chars | ✅ |
| `student_name` | string | 2–100 chars | ✅ |
| `attendance_percentage` | float | 0–100 | ✅ |
| `study_hours_per_week` | float | 0–168 | ✅ |
| `assignment_score` | float | 0–100 | ✅ |
| `quiz_marks` | float | 0–100 | ✅ |
| `previous_gpa` | float | 0.0–4.0 | ✅ |

**Success Response (200)**
```json
{
  "success": true,
  "message": "Prediction successful",
  "timestamp": "2026-06-12T10:30:45Z",
  "prediction": {
    "prediction_id":        42,
    "student_id":           "STU001",
    "student_name":         "John Doe",
    "predicted_grade":      81.4,
    "confidence_score":     0.923,
    "risk_level":           "low",
    "rf_prediction":        80.9,
    "xgb_prediction":       82.2,
    "prediction_timestamp": "2026-06-12T10:30:45Z",
    "input_features": {
      "attendance_percentage": 85.5,
      "study_hours_per_week":  15.0,
      "assignment_score":      78.0,
      "quiz_marks":            82.0,
      "previous_gpa":          3.5
    }
  }
}
```

**Risk Levels**
| Level | Grade Range | Action |
|-------|-------------|--------|
| `low` | ≥ 75 | No intervention needed |
| `medium` | 60–74 | Recommend additional support |
| `high` | 50–59 | Urgent academic counselling |
| `critical` | < 50 | Immediate intervention required |

**Error Example (400)**
```json
{
  "success": false,
  "error": "Validation failed",
  "code": "VALIDATION_ERROR",
  "timestamp": "...",
  "errors": [
    "'attendance_percentage' must be between 0.0 and 100.0, got 150.0."
  ]
}
```

---

### GET `/api/history`
Retrieve all predictions for a student.

**Query Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `student_id` | string | ✅ | Student ID (3–20 alphanumeric) |
| `limit` | integer | ❌ | Max records to return (default 50, max 200) |

**Example**
```
GET /api/history?student_id=STU001&limit=10
```

**Success Response (200)**
```json
{
  "success": true,
  "message": "History retrieved successfully",
  "student_id": "STU001",
  "student_name": "John Doe",
  "prediction_count": 5,
  "predictions": [
    {
      "prediction_id":         42,
      "student_id":            "STU001",
      "predicted_grade":       81.4,
      "confidence_score":      0.923,
      "risk_level":            "low",
      "model_used":            "rf+xgboost-ensemble",
      "attendance_percentage": 85.5,
      "study_hours":           15.0,
      "assignment_score":      78.0,
      "quiz_marks":            82.0,
      "previous_gpa":          3.5,
      "prediction_timestamp":  "2026-06-12T10:30:45Z"
    }
  ]
}
```

---

### GET `/api/stats`
Retrieve aggregate system statistics.

**Success Response (200)**
```json
{
  "success": true,
  "message": "Stats retrieved successfully",
  "stats": {
    "total_predictions":   150,
    "total_students":      45,
    "avg_predicted_grade": 79.2,
    "system_uptime":       "2 days 5 hours",
    "database_size_mb":    2.5,
    "last_prediction":     "2026-06-12T10:30:45Z",
    "model_loaded":        true,
    "timestamp":           "2026-06-12T10:35:00Z"
  }
}
```

---

### GET `/api/health`
Liveness / readiness check endpoint.

**Success Response (200)**
```json
{
  "status":       "healthy",
  "database":     "connected",
  "model_loaded": true,
  "uptime":       "2 days 5 hours",
  "timestamp":    "2026-06-12T10:30:45Z"
}
```

**Degraded Response (503)**
```json
{
  "status":       "degraded",
  "database":     "error: ...",
  "model_loaded": false,
  "uptime":       "5 minutes",
  "timestamp":    "..."
}
```

---

### GET `/api/recent`
Returns the N most recent predictions across all students (used by the dashboard).

**Query Parameters**
| Parameter | Default | Max |
|-----------|---------|-----|
| `limit` | 10 | 50 |

---

## Error Codes Reference

| Code | HTTP | Description |
|------|------|-------------|
| `VALIDATION_ERROR` | 400 | Input field failed validation |
| `INVALID_JSON` | 400 | Request body is not valid JSON |
| `STUDENT_NOT_FOUND` | 404 | No records for given student_id |
| `MODEL_ERROR` | 500 | ML model prediction failed |
| `DB_ERROR` | 500 | Database operation failed |
| `NOT_FOUND` | 404 | Endpoint does not exist |
| `METHOD_NOT_ALLOWED` | 405 | Wrong HTTP method |
| `INTERNAL_ERROR` | 500 | Unhandled server error |
