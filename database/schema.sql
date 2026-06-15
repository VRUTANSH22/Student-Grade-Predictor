-- ============================================================
--  Student Performance Predictor — MySQL Database Schema
--  Compatible with MySQL 8.0+ and SQLite 3.x
--  Run:  mysql -u root -p < database/schema.sql
-- ============================================================

-- Create and select the database (MySQL only; SQLite ignores)
CREATE DATABASE IF NOT EXISTS student_predictor
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE student_predictor;

-- ──────────────────────────────────────────────────
--  1. students
--     One row per unique student (upserted on predict)
-- ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS students (
    student_id      VARCHAR(20)  PRIMARY KEY,
    student_name    VARCHAR(100) NOT NULL,
    email           VARCHAR(100) DEFAULT NULL,
    enrollment_date TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- ──────────────────────────────────────────────────
--  2. predictions
--     One row per prediction call
-- ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id          INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
    student_id             VARCHAR(20)   NOT NULL,
    predicted_grade        DECIMAL(5,2)  NOT NULL,
    confidence_score       DECIMAL(4,3)  NOT NULL,
    attendance_percentage  DECIMAL(5,2)  DEFAULT NULL,
    study_hours            DECIMAL(5,2)  DEFAULT NULL,
    assignment_score       DECIMAL(5,2)  DEFAULT NULL,
    quiz_marks             DECIMAL(5,2)  DEFAULT NULL,
    previous_gpa           DECIMAL(3,2)  DEFAULT NULL,
    risk_level             VARCHAR(20)   DEFAULT NULL,
    model_used             VARCHAR(50)   DEFAULT 'ensemble',
    prediction_timestamp   TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    created_at             TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_student_id  (student_id),
    INDEX idx_timestamp   (prediction_timestamp)
);

-- ──────────────────────────────────────────────────
--  3. api_logs
--     One row per API request (success or failure)
-- ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_logs (
    log_id           INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    endpoint         VARCHAR(100) DEFAULT NULL,
    method           VARCHAR(10)  DEFAULT NULL,
    student_id       VARCHAR(20)  DEFAULT NULL,
    request_data     JSON         DEFAULT NULL,
    response_status  INT          DEFAULT NULL,
    execution_time_ms INT         DEFAULT NULL,
    error_message    TEXT         DEFAULT NULL,
    remote_ip        VARCHAR(45)  DEFAULT NULL,
    user_agent       TEXT         DEFAULT NULL,
    logged_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_endpoint  (endpoint),
    INDEX idx_logged_at (logged_at)
);

-- ──────────────────────────────────────────────────
--  4. system_stats  (single-row snapshot, updated on each /api/stats call)
-- ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system_stats (
    stat_id              INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    total_predictions    INT          DEFAULT 0,
    total_students       INT          DEFAULT 0,
    avg_predicted_grade  DECIMAL(5,2) DEFAULT NULL,
    database_size_mb     DECIMAL(10,2) DEFAULT NULL,
    last_updated         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                         ON UPDATE CURRENT_TIMESTAMP
);

-- Seed an initial stats row so updates work via row-0
INSERT IGNORE INTO system_stats (stat_id, total_predictions, total_students)
VALUES (1, 0, 0);
