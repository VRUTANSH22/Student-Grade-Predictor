"""
app/database.py — SQLAlchemy Database Layer
============================================
Provides the SQLAlchemy engine, session factory, and ORM table definitions.
Works with both SQLite (development) and MySQL 8.0+ (production).
"""

import json
import datetime
from contextlib import contextmanager

from sqlalchemy import (
    create_engine,
    Column, Integer, String, Float, Text, DateTime, JSON,
    Index, inspect, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

# ── ORM base ──────────────────────────────────────────────────────────────────
Base = declarative_base()


# ── ORM Models ────────────────────────────────────────────────────────────────

class Student(Base):
    __tablename__ = "students"

    student_id      = Column(String(20), primary_key=True)
    student_name    = Column(String(100), nullable=False)
    email           = Column(String(100), nullable=True)
    enrollment_date = Column(DateTime, default=datetime.datetime.utcnow)
    created_at      = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "student_id":      self.student_id,
            "student_name":    self.student_name,
            "email":           self.email,
            "enrollment_date": self.enrollment_date.isoformat() if self.enrollment_date else None,
            "created_at":      self.created_at.isoformat() if self.created_at else None,
        }


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        Index("idx_student_id", "student_id"),
        Index("idx_timestamp",  "prediction_timestamp"),
    )

    prediction_id         = Column(Integer, primary_key=True, autoincrement=True)
    student_id            = Column(String(20), nullable=False)
    predicted_grade       = Column(Float, nullable=False)
    confidence_score      = Column(Float, nullable=False)
    attendance_percentage = Column(Float, nullable=True)
    study_hours           = Column(Float, nullable=True)
    assignment_score      = Column(Float, nullable=True)
    quiz_marks            = Column(Float, nullable=True)
    previous_gpa          = Column(Float, nullable=True)
    risk_level            = Column(String(20), nullable=True)
    model_used            = Column(String(50), default="ensemble")
    prediction_timestamp  = Column(DateTime, default=datetime.datetime.utcnow)
    created_at            = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "prediction_id":         self.prediction_id,
            "student_id":            self.student_id,
            "predicted_grade":       round(self.predicted_grade, 2),
            "confidence_score":      round(self.confidence_score, 3),
            "risk_level":            self.risk_level,
            "model_used":            self.model_used,
            "attendance_percentage": self.attendance_percentage,
            "study_hours":           self.study_hours,
            "assignment_score":      self.assignment_score,
            "quiz_marks":            self.quiz_marks,
            "previous_gpa":          self.previous_gpa,
            "prediction_timestamp":  (
                self.prediction_timestamp.isoformat() + "Z"
                if self.prediction_timestamp else None
            ),
        }


class ApiLog(Base):
    __tablename__ = "api_logs"
    __table_args__ = (
        Index("idx_endpoint",   "endpoint"),
        Index("idx_logged_at",  "logged_at"),
    )

    log_id            = Column(Integer, primary_key=True, autoincrement=True)
    endpoint          = Column(String(100), nullable=True)
    method            = Column(String(10),  nullable=True)
    student_id        = Column(String(20),  nullable=True)
    request_data      = Column(Text,        nullable=True)   # stored as JSON string
    response_status   = Column(Integer,     nullable=True)
    execution_time_ms = Column(Integer,     nullable=True)
    error_message     = Column(Text,        nullable=True)
    remote_ip         = Column(String(45),  nullable=True)
    user_agent        = Column(Text,        nullable=True)
    logged_at         = Column(DateTime,    default=datetime.datetime.utcnow)


class SystemStats(Base):
    __tablename__ = "system_stats"

    stat_id             = Column(Integer, primary_key=True, autoincrement=True)
    total_predictions   = Column(Integer, default=0)
    total_students      = Column(Integer, default=0)
    avg_predicted_grade = Column(Float,   nullable=True)
    database_size_mb    = Column(Float,   nullable=True)
    last_updated        = Column(DateTime, default=datetime.datetime.utcnow,
                                 onupdate=datetime.datetime.utcnow)


# ── Engine & Session Factory ──────────────────────────────────────────────────

_engine = None
_SessionFactory = None


def init_db(database_uri: str, echo: bool = False):
    """
    Initialise the SQLAlchemy engine and create all tables.
    Call once at application startup.
    """
    global _engine, _SessionFactory

    connect_args = {}
    if database_uri.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    _engine = create_engine(
        database_uri,
        echo=echo,
        connect_args=connect_args,
        pool_pre_ping=True,       # detect stale connections
        pool_recycle=3600,        # recycle connections every hour
    )

    # Create tables if they don't exist
    Base.metadata.create_all(_engine)

    # Seed system_stats row (id=1) if missing
    _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)
    with _SessionFactory() as session:
        row = session.get(SystemStats, 1)
        if row is None:
            session.add(SystemStats(stat_id=1, total_predictions=0, total_students=0))
            session.commit()

    return _engine


def get_engine():
    """Return the shared SQLAlchemy engine."""
    if _engine is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _engine


@contextmanager
def get_db_session():
    """Context manager that yields a SQLAlchemy session and handles commit/rollback."""
    if _SessionFactory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    session: Session = _SessionFactory()
    try:
        yield session
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


# ── Helper DB Operations ──────────────────────────────────────────────────────

def upsert_student(session: Session, student_id: str, student_name: str) -> Student:
    """Insert or fetch-and-update a student record."""
    student = session.get(Student, student_id)
    if student is None:
        student = Student(student_id=student_id, student_name=student_name)
        session.add(student)
    else:
        student.student_name = student_name
    return student


def save_prediction(session: Session, data: dict) -> Prediction:
    """Persist a prediction record and return it."""
    pred = Prediction(
        student_id            = data["student_id"],
        predicted_grade       = data["predicted_grade"],
        confidence_score      = data["confidence_score"],
        attendance_percentage = data.get("attendance_percentage"),
        study_hours           = data.get("study_hours"),
        assignment_score      = data.get("assignment_score"),
        quiz_marks            = data.get("quiz_marks"),
        previous_gpa          = data.get("previous_gpa"),
        risk_level            = data.get("risk_level"),
        model_used            = data.get("model_used", "ensemble"),
    )
    session.add(pred)
    return pred


def log_api_call(
    session: Session,
    endpoint: str,
    method: str,
    student_id: str | None,
    request_data: dict | None,
    response_status: int,
    execution_time_ms: int,
    error_message: str | None,
    remote_ip: str | None,
    user_agent: str | None,
) -> ApiLog:
    """Persist one API log entry."""
    entry = ApiLog(
        endpoint          = endpoint,
        method            = method,
        student_id        = student_id,
        request_data      = json.dumps(request_data) if request_data else None,
        response_status   = response_status,
        execution_time_ms = execution_time_ms,
        error_message     = error_message,
        remote_ip         = remote_ip,
        user_agent        = user_agent,
    )
    session.add(entry)
    return entry


def refresh_system_stats(session: Session) -> dict:
    """
    Recompute aggregate stats from DB and update the system_stats row.
    Returns the stats dict.
    """
    total_predictions = session.query(Prediction).count()
    total_students    = session.query(Student).count()

    grades = [r.predicted_grade for r in session.query(Prediction.predicted_grade).all()]
    avg_grade = round(sum(grades) / len(grades), 2) if grades else None

    stats_row = session.get(SystemStats, 1)
    if stats_row is None:
        stats_row = SystemStats(stat_id=1)
        session.add(stats_row)

    stats_row.total_predictions   = total_predictions
    stats_row.total_students      = total_students
    stats_row.avg_predicted_grade = avg_grade
    stats_row.last_updated        = datetime.datetime.utcnow()

    return {
        "total_predictions":   total_predictions,
        "total_students":      total_students,
        "avg_predicted_grade": avg_grade,
        "last_updated":        stats_row.last_updated.isoformat() + "Z",
    }
