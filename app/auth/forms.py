import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError


def no_control_characters(form, field):
    """Reject null bytes or control characters in text inputs."""
    if field.data and (re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", field.data)):
        raise ValidationError("Input contains forbidden control characters.")


def password_complexity_check(form, field):
    """Enforce at least 8 chars, max 128 chars, and non-trivial password."""
    pwd = field.data or ""
    if len(pwd) < 8:
        raise ValidationError("Password must be at least 8 characters.")
    if len(pwd) > 128:
        raise ValidationError("Password exceeds maximum allowed length of 128 characters.")


class LoginForm(FlaskForm):
    email = StringField(
        "Email address",
        validators=[DataRequired(), Length(max=255), Email(check_deliverability=False), no_control_characters],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(max=128), no_control_characters],
    )
    remember_me = BooleanField("Remember me", default=True)
    submit = SubmitField("Sign in")


class SignupForm(FlaskForm):
    """Candidate signup only — recruiters register via the recruiters page."""
    full_name = StringField(
        "Full name",
        validators=[DataRequired(), Length(min=2, max=150), no_control_characters],
    )
    email = StringField(
        "Email address",
        validators=[DataRequired(), Length(max=255), Email(check_deliverability=False), no_control_characters],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), password_complexity_check],
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    agree_terms = BooleanField(
        "I agree to the Terms & Conditions and Privacy Policy",
        validators=[DataRequired(message="You must agree to continue.")],
    )
    submit = SubmitField("Create account")


class ResetPasswordRequestForm(FlaskForm):
    email = StringField(
        "Email address",
        validators=[DataRequired(), Length(max=255), Email(check_deliverability=False), no_control_characters],
    )
    submit = SubmitField("Send reset link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField(
        "New password",
        validators=[DataRequired(), password_complexity_check],
    )
    confirm_password = PasswordField(
        "Confirm new password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Reset password")
