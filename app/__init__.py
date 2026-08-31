import os
import logging
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf import CSRFProtect

from app.config import config_by_name
from app.utils.security import limiter

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()


def create_app(config_name=None):
    """Application factory with security rate-limiting and error handlers."""
    config_name = config_name or os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Logging setup
    if not app.debug and not app.testing:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s in %(module)s: %(message)s",
        )

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "info"

    # --- Models must be imported before blueprints so relationships resolve ---
    from app.models.user import User  # noqa: F401
    from app.models.recruiter_profile import RecruiterProfile  # noqa: F401
    from app.models.resume import Resume  # noqa: F401
    from app.models.job import Job  # noqa: F401
    from app.models.application import Application  # noqa: F401
    from app.models.career_entry import CareerEntry  # noqa: F401
    from app.models.saved_job import SavedJob  # noqa: F401
    from app.models.application_event import ApplicationEvent  # noqa: F401
    from app.models.notification import Notification  # noqa: F401
    from app.models.admin_audit_log import AdminAuditLog  # noqa: F401
    from app.models.admin_setting import AdminSetting  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        user = User.query.get(int(user_id))
        if user and not user.is_active_account:
            return None
        return user

    # --- Blueprints ---
    from app.main.routes import main_bp
    from app.auth.routes import auth_bp
    from app.candidate.routes import candidate_bp
    from app.recruiter.routes import recruiter_bp
    from app.admin.routes import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(candidate_bp, url_prefix="/candidate")
    app.register_blueprint(recruiter_bp, url_prefix="/recruiter")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    from app.utils.filters import register_filters
    register_filters(app)

    # --- Global Error Handlers (Information Leakage Prevention) ---
    def _is_json_request():
        return (
            request.is_json
            or request.path.startswith("/api/")
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or "application/json" in request.headers.get("Accept", "")
        )

    @app.errorhandler(400)
    def bad_request_error(error):
        if _is_json_request():
            return jsonify({"status": "error", "error": "Bad Request", "message": str(error.description if hasattr(error, 'description') else "Invalid request data.")}), 400
        return render_template("errors/400.html", error_message=getattr(error, 'description', None)), 400

    @app.errorhandler(403)
    def forbidden_error(error):
        if _is_json_request():
            return jsonify({"status": "error", "error": "Forbidden", "message": "Access restricted."}), 403
        return render_template("errors/403.html", error_message=getattr(error, 'description', None)), 403

    @app.errorhandler(404)
    def not_found_error(error):
        if _is_json_request():
            return jsonify({"status": "error", "error": "Not Found", "message": "Resource not found."}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def ratelimit_handler(e):
        retry_after = getattr(e, "retry_after", None) or 60
        if _is_json_request():
            resp = jsonify({
                "status": "error",
                "error": "Rate limit exceeded",
                "message": "Too many requests. Please slow down.",
                "retry_after": retry_after,
            })
            resp.status_code = 429
            resp.headers["Retry-After"] = str(retry_after)
            return resp
        return render_template("errors/429.html", retry_after=retry_after, error_message=str(e.description if hasattr(e, 'description') else "")), 429

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error("Unhandled Exception: %s", error, exc_info=True)
        db.session.rollback()
        if _is_json_request():
            return jsonify({"status": "error", "error": "Internal Server Error", "message": "An unexpected error occurred. No diagnostic details leaked."}), 500
        return render_template("errors/500.html"), 500

    return app
