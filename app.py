"""
app.py — Application Entry Point
==================================
Run with:
    python app.py                          # development server
    gunicorn --workers 4 --bind 0.0.0.0:5000 app:app   # production
"""

from app import create_app
from config import get_config

# ── Create the Flask application ──────────────────────────────────────────────
config_class = get_config()
app = create_app(config_class)

if __name__ == "__main__":
    print(
        "\n"
        "  +--------------------------------------------------+\n"
        "  |   Student Performance Predictor -- Flask API    |\n"
        "  |   Vrutansh Tagadiya | Final Year B.Tech (IT)   |\n"
        "  +--------------------------------------------------+\n"
        f"  |  http://{config_class.HOST}:{config_class.PORT}                        |\n"
        f"  |  Swagger: http://localhost:{config_class.PORT}/apidocs        |\n"
        f"  |  DB: {config_class.get_db_engine_name():<45}|\n"
        "  +--------------------------------------------------+\n"
    )
    app.run(
        host  = config_class.HOST,
        port  = config_class.PORT,
        debug = config_class.DEBUG,
    )
