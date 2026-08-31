from functools import wraps

from flask import abort, flash, redirect, url_for
from flask_login import current_user


def role_required(*roles):
    """Restrict a route to logged-in users with one of the given roles.

    Also verifies the account has not been disabled since login — even if the
    session cookie is still valid, a disabled account is immediately rejected.

    Usage: @role_required("candidate")
           @role_required("recruiter", "admin")
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if not current_user.is_active_account:
                # Session still valid but account was disabled after login
                from flask_login import logout_user
                logout_user()
                flash("Your account has been disabled. Contact support.", "error")
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def approved_recruiter_required(view_func):
    """Restrict a route to recruiters whose company has been approved.

    Also checks account is still active on every request.
    """
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_active_account:
            from flask_login import logout_user
            logout_user()
            flash("Your account has been disabled. Contact support.", "error")
            return redirect(url_for("auth.login"))
        if not current_user.is_recruiter:
            abort(403)
        if not current_user.is_approved_recruiter:
            flash("Your company is still pending admin approval.", "info")
            return redirect(url_for("recruiter.dashboard"))
        return view_func(*args, **kwargs)
    return wrapped
