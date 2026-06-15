"""
config.py — Application Configuration Management
=================================================
Reads all settings from environment variables (via .env file).
Supports Development (SQLite) and Production (MySQL) modes.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
load_dotenv()


class BaseConfig:
    """Base configuration shared by all environments."""

    # Flask core
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    JSON_SORT_KEYS: bool = False

    # Paths
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    LOG_DIR: str = os.path.join(BASE_DIR, os.getenv("LOG_DIR", "logs"))
    MODEL_DIR: str = os.path.join(BASE_DIR, os.getenv("MODEL_DIR", "models"))

    # ML ensemble weights
    RF_WEIGHT: float = float(os.getenv("RF_WEIGHT", "0.6"))
    XGB_WEIGHT: float = float(os.getenv("XGB_WEIGHT", "0.4"))

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "5000"))

    # Database engine selection
    USE_SQLITE: bool = os.getenv("USE_SQLITE", "true").lower() == "true"

    # MySQL settings (used when USE_SQLITE=false)
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_NAME: str = os.getenv("DB_NAME", "student_predictor")
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # SQLite settings (used when USE_SQLITE=true)
    SQLITE_DB_PATH: str = os.path.join(
        BASE_DIR, os.getenv("SQLITE_DB_PATH", "student_predictor.db")
    )

    @classmethod
    def get_database_uri(cls) -> str:
        """Return the correct SQLAlchemy database URI based on USE_SQLITE flag."""
        if cls.USE_SQLITE:
            return f"sqlite:///{cls.SQLITE_DB_PATH}"
        return (
            f"mysql+pymysql://{cls.DB_USER}:{cls.DB_PASSWORD}"
            f"@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
            f"?charset=utf8mb4"
        )

    @classmethod
    def get_db_engine_name(cls) -> str:
        return "SQLite" if cls.USE_SQLITE else "MySQL"


class DevelopmentConfig(BaseConfig):
    """Development configuration — uses SQLite, debug mode enabled."""
    DEBUG: bool = True
    TESTING: bool = False
    SQLALCHEMY_ECHO: bool = False  # Set True to log all SQL queries


class ProductionConfig(BaseConfig):
    """Production configuration — MySQL expected, debug disabled."""
    DEBUG: bool = False
    TESTING: bool = False
    USE_SQLITE: bool = os.getenv("USE_SQLITE", "false").lower() == "true"


class TestingConfig(BaseConfig):
    """Testing configuration — in-memory SQLite, testing mode enabled."""
    DEBUG: bool = True
    TESTING: bool = True
    USE_SQLITE: bool = True
    SQLITE_DB_PATH: str = ":memory:"

    @classmethod
    def get_database_uri(cls) -> str:
        return "sqlite:///:memory:"


# ── Config registry ────────────────────────────────────────────────────────────
CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config() -> type:
    """Return the appropriate config class based on FLASK_ENV."""
    env = os.getenv("FLASK_ENV", "development").lower()
    return CONFIG_MAP.get(env, DevelopmentConfig)
