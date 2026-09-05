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

    try:
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    except OSError:
        # Fallback to /tmp on serverless environments (e.g. Vercel, AWS Lambda)
        app.config["UPLOAD_FOLDER"] = "/tmp/uploads"
        try:
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        except OSError:
            pass

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
    from app.models.support_ticket import SupportTicket, SupportTicketMessage  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        # user_id is User.get_id()'s "<id>|<password stamp>" — reject
        # anything that doesn't carry a matching stamp so that a password
        # change invalidates sessions/remember-cookies issued before it,
        # not just future logins with the old password (see
        # User.get_id/User.password_stamp). Sessions from before this
        # check existed have no "|" and are rejected the same way, which
        # is a one-time forced re-login for anyone already signed in.
        raw_id, sep, stamp = str(user_id).partition("|")
        if not sep:
            return None
        try:
            user = User.query.get(int(raw_id))
        except (TypeError, ValueError):
            return None
        if not user or not user.is_active_account:
            return None
        if stamp != user.password_stamp:
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

    # --- Maintenance Mode Enforcement ---
    @app.before_request
    def check_maintenance_mode():
        if app.testing:
            return
        if request.path.startswith("/static/") or request.endpoint in ("auth.login", "auth.logout"):
            return
        from flask_login import current_user
        if current_user.is_authenticated and current_user.is_admin:
            return
        try:
            from app.models.admin_setting import AdminSetting
            if AdminSetting.get("maintenance_mode", "false").lower() == "true":
                if _is_json_request():
                    return jsonify({"status": "error", "error": "Maintenance Mode", "message": "Zentra is undergoing scheduled maintenance."}), 503
                return render_template("errors/503.html"), 503
        except Exception:
            pass

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
    from flask import g
    import base64
    import secrets

    @app.before_request
    def set_csp_nonce():
        g.csp_nonce = base64.b64encode(secrets.token_bytes(16)).decode("utf-8")

    @app.context_processor
    def inject_csp_nonce():
        return dict(csp_nonce=getattr(g, "csp_nonce", ""))

    # --- Security Headers & Cache-Control Enforcement ---
    @app.after_request
    def set_security_and_cache_headers(response):
        # 1. Core Security Headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

        # Content-Security-Policy (Strict allowlist - No wildcards, Nonce-protected)
        nonce = getattr(g, "csp_nonce", "")
        nonce_str = f"'nonce-{nonce}'" if nonce else ""
        script_srcs = ["'self'", "https://cdn.jsdelivr.net"]
        style_srcs = ["'self'", "https://fonts.googleapis.com", "https://cdn.jsdelivr.net"]
        if nonce_str:
            script_srcs.append(nonce_str)
            style_srcs.append(nonce_str)

        csp_directives = [
            "default-src 'self'",
            f"script-src {' '.join(script_srcs)}",
            f"style-src {' '.join(style_srcs)}",
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net data:",
            "img-src 'self' data: https: blob:",
            "connect-src 'self' https://generativelanguage.googleapis.com https://api.groq.com",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # 2. Cache-Control
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            from flask_login import current_user
            is_auth = False
            try:
                is_auth = bool(current_user and current_user.is_authenticated)
            except Exception:
                is_auth = False

            is_sensitive_path = (
                request.path.startswith("/candidate")
                or request.path.startswith("/recruiter")
                or request.path.startswith("/admin")
                or request.path.startswith("/auth")
                or request.path.startswith("/api")
            )

            if is_auth or is_sensitive_path or "Set-Cookie" in response.headers:
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
            else:
                response.headers["Cache-Control"] = "no-cache, must-revalidate, max-age=0, private"

        return response

    return app
