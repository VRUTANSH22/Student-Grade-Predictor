"""
app/__init__.py — Flask Application Factory
=============================================
Creates and configures the Flask application instance.
All extensions (CORS, Flasgger, DB, Models) are initialised here.
"""

import logging
from flask import Flask
from flask_cors import CORS
from flasgger import Swagger

from config import get_config
from app.logger   import setup_logging
from app.database import init_db
from app.models   import model_manager
from app.utils    import set_start_time

logger = logging.getLogger(__name__)

# ── Swagger / OpenAPI configuration ──────────────────────────────────────────
SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint":    "apispec",
            "route":       "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui":       True,
    "specs_route":      "/apidocs",
}

SWAGGER_TEMPLATE = {
    "info": {
        "title":       "Student Performance Predictor API",
        "description": (
            "RESTful API for predicting student academic performance using "
            "Random Forest and XGBoost ensemble models."
        ),
        "version": "1.0.0",
        "contact": {
            "name":  "Vrutansh Tagadiya",
            "email": "vrutansh@example.com",
        },
    },
    "tags": [
        {"name": "Predictions", "description": "ML prediction endpoints"},
        {"name": "History",     "description": "Student history retrieval"},
        {"name": "Monitoring",  "description": "System health and stats"},
    ],
    "basePath": "/",
    "schemes":  ["http", "https"],
}


def create_app(config_class=None):
    """
    Flask application factory.

    Args:
        config_class: Config class to use. Defaults to environment-based selection.

    Returns:
        Configured Flask app instance.
    """
    if config_class is None:
        config_class = get_config()

    # ── Logging (first, so all other init steps are logged) ──────────────
    setup_logging(log_dir=config_class.LOG_DIR)

    # ── Flask app ─────────────────────────────────────────────────────────
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config["SECRET_KEY"] = config_class.SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = config_class.get_database_uri()
    app.config["JSON_SORT_KEYS"] = False

    # ── Extensions ────────────────────────────────────────────────────────
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)

    # ── Database ──────────────────────────────────────────────────────────
    db_uri = config_class.get_database_uri()
    try:
        init_db(db_uri, echo=getattr(config_class, "SQLALCHEMY_ECHO", False))
        logger.info(
            "Database initialised",
            extra={"engine": config_class.get_db_engine_name(), "uri_prefix": db_uri[:30]}
        )
    except Exception as exc:
        logger.error("Database initialisation failed: %s", exc)
        # App still starts; health endpoint will report DB as down

    # ── Load ML models ────────────────────────────────────────────────────
    try:
        model_manager.load(
            model_dir  = config_class.MODEL_DIR,
            rf_weight  = config_class.RF_WEIGHT,
            xgb_weight = config_class.XGB_WEIGHT,
        )
        logger.info("ML models loaded successfully")
    except FileNotFoundError as exc:
        logger.warning(
            "ML models not found — run `python train_models.py` first. %s", exc
        )
    except Exception as exc:
        logger.error("ML model loading failed: %s", exc)

    # ── Register blueprints & error handlers ──────────────────────────────
    from app.routes import bp, register_error_handlers
    app.register_blueprint(bp)
    register_error_handlers(app)

    # ── Record startup time for uptime calculation ────────────────────────
    set_start_time()

    logger.info(
        "Flask app created",
        extra={
            "env":          getattr(config_class, "FLASK_ENV", "unknown"),
            "debug":        getattr(config_class, "DEBUG", False),
            "db_engine":    config_class.get_db_engine_name(),
            "models_ready": model_manager.is_loaded,
        }
    )

    return app
