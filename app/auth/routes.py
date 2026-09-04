from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app import db
from app.models.user import User
from app.auth.forms import LoginForm, SignupForm, ResetPasswordRequestForm, ResetPasswordForm
from app.utils.security import limiter, login_tracker

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")

_RESET_SALT = "password-reset"
_RESET_MAX_AGE_SECONDS = 3600  # 1 hour


def _generate_reset_token(user):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    payload = {
        "email": user.email,
        "pwd_fp": user.password_hash[-12:] if user.password_hash else "",
    }
    return serializer.dumps(payload, salt=_RESET_SALT)


def _verify_reset_token(token):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        payload = serializer.loads(token, salt=_RESET_SALT, max_age=_RESET_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired, Exception):
        return None

    if not isinstance(payload, dict) or "email" not in payload:
        return None

    user = User.query.filter_by(email=payload["email"]).first()
    if not user or not user.is_active_account:
        return None

    # Enforce one-time use: invalidates token if password was already changed
    if payload.get("pwd_fp") != (user.password_hash[-12:] if user.password_hash else ""):
        return None

    return user


def _redirect_for_role(user):
    if user.is_admin:
        return redirect(url_for("admin.dashboard"))
    if user.is_recruiter:
        return redirect(url_for("recruiter.dashboard"))
    return redirect(url_for("candidate.dashboard"))


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config.get("RATELIMIT_AUTH", "5 per minute; 20 per hour"))
def login():
    if current_user.is_authenticated:
        return _redirect_for_role(current_user)

    login_form = LoginForm(prefix="login")
    signup_form = SignupForm(prefix="signup")

    if login_form.submit.data and login_form.validate_on_submit():
        ip = request.remote_addr or ""
        email = (login_form.email.data or "").lower().strip()

        # Check exponential backoff cooldown
        backoff = login_tracker.get_backoff_info(ip=ip, email=email)
        if backoff["is_throttled"]:
            flash(
                f"Too many failed login attempts. Please wait {backoff['remaining_cooldown']} seconds before trying again.",
                "error",
            )
            return render_template("auth/login.html", login_form=login_form, signup_form=signup_form)

        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(login_form.password.data):
            login_tracker.record_failure(ip=ip, email=email)
            flash("Incorrect email or password.", "error")
        elif not user.is_active_account:
            login_tracker.record_failure(ip=ip, email=email)
            flash("This account has been disabled. Contact support.", "error")
        else:
            login_tracker.record_success(ip=ip, email=email)
            login_user(user, remember=login_form.remember_me.data)
            next_page = request.args.get("next")
            if next_page and next_page.startswith("/") and not next_page.startswith("//"):
                return redirect(next_page)
            return _redirect_for_role(user)

    return render_template("auth/login.html", login_form=login_form, signup_form=signup_form)


@auth_bp.route("/signup", methods=["POST"])
@limiter.limit(lambda: current_app.config.get("RATELIMIT_AUTH", "5 per minute; 20 per hour"))
def signup():
    """Candidate signup only. Recruiters register via recruiter.register."""
    login_form = LoginForm(prefix="login")
    signup_form = SignupForm(prefix="signup")

    if signup_form.validate_on_submit():
        from app.models.admin_setting import AdminSetting
        if AdminSetting.get("registration_open", "true").lower() == "false":
            flash("Candidate registration is currently disabled by administrator.", "error")
            return render_template("auth/login.html", login_form=login_form, signup_form=signup_form)

        existing = User.query.filter_by(email=signup_form.email.data.lower().strip()).first()
        if existing:
            flash("An account with this email already exists.", "error")
        else:
            user = User(
                full_name=signup_form.full_name.data.strip(),
                email=signup_form.email.data.lower().strip(),
                role=User.ROLE_CANDIDATE,
            )
            user.set_password(signup_form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to Zentra!", "success")
            return redirect(url_for("candidate.dashboard"))

    return render_template("auth/login.html", login_form=login_form, signup_form=signup_form)


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    flash("You've been signed out.", "info")
    return redirect(url_for("main.landing"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config.get("RATELIMIT_AUTH", "5 per minute; 20 per hour"))
def forgot_password():
    if current_user.is_authenticated:
        return _redirect_for_role(current_user)

    form = ResetPasswordRequestForm()
    reset_link = None

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        is_dev = current_app.debug or current_app.testing or current_app.config.get("ENV") == "development"
        if user and user.is_active_account:
            token = _generate_reset_token(user)
            if is_dev:
                reset_link = url_for("auth.reset_password", token=token, _external=True)
                flash("Development mode: A reset link has been generated below.", "info")
            else:
                # In production, send email (or log safely) without exposing link in HTML
                current_app.logger.info(f"Password reset requested for {user.email}")
                flash("If that email is registered, instructions to reset your password have been sent.", "info")
        else:
            flash("If that email is registered, instructions to reset your password have been sent.", "info")

    return render_template("auth/forgot_password.html", form=form, reset_link=reset_link)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config.get("RATELIMIT_AUTH", "5 per minute; 20 per hour"))
def reset_password(token):
    user = _verify_reset_token(token)
    if user is None:
        flash("That reset link is invalid or has expired. Request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Password updated — you can log in now.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)
