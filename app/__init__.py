import os
from datetime import timedelta

from flask import Flask, render_template, session

from config import Config
from app.database.supabase_client import init_local_schema, get_supabase_client
from app.services.auth_service import AuthService


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.permanent_session_lifetime = timedelta(days=14)

    # Initialize local SQLite only when Supabase is not configured.
    # Production/Vercel should use Supabase as the persistent database.
    if not (Config.SUPABASE_URL and Config.SUPABASE_KEY):
        try:
            init_local_schema()
        except Exception as e:
            app.logger.warning("Local schema init warning: %s", e)

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.student import student_bp
    from app.routes.faculty import faculty_bp
    from app.routes.quizzes import quizzes_bp
    from app.routes.questions import questions_bp
    from app.routes.results import results_bp
    from app.routes.analytics import analytics_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(faculty_bp)
    app.register_blueprint(quizzes_bp)
    app.register_blueprint(questions_bp)
    app.register_blueprint(results_bp)
    app.register_blueprint(analytics_bp)

    # Root Home Route
    @app.route("/")
    def home():
        student = AuthService.get_current_student()
        faculty = AuthService.get_current_faculty()
        return render_template("home.html", student=student, faculty=faculty)

    # Context processors for templates
    @app.context_processor
    def inject_global_data():
        return {
            "current_student": AuthService.get_current_student(),
            "current_faculty": AuthService.get_current_faculty(),
            "is_supabase_connected": get_supabase_client() is not None,
            "current_year": 2026,
        }

    # Template filters
    @app.template_filter("format_date")
    def format_date_filter(val):
        if not val:
            return "-"

        try:
            import datetime

            val_clean = str(val).replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(val_clean)
            return dt.strftime("%d %b %Y, %I:%M %p")
        except Exception:
            return str(val)[:16]

    @app.template_filter("round_val")
    def round_val_filter(val, decimals=1):
        try:
            return f"{float(val):.{decimals}f}"
        except Exception:
            return val

    return app