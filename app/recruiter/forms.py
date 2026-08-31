import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional, URL, ValidationError


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


class RecruiterRegistrationForm(FlaskForm):
    # Company details
    company_name = StringField("Company name", validators=[DataRequired(), Length(min=2, max=200), no_control_characters])
    industry = SelectField(
        "Industry",
        choices=[
            ("technology", "Technology"), ("finance", "Finance"),
            ("healthcare", "Healthcare"), ("manufacturing", "Manufacturing"),
            ("retail", "Retail"), ("other", "Other"),
        ],
    )
    company_size = SelectField(
        "Company size",
        choices=[
            ("1-10", "1–10 employees"), ("11-50", "11–50 employees"),
            ("51-200", "51–200 employees"), ("201-500", "201–500 employees"),
            ("500+", "500+ employees"),
        ],
    )
    company_website = StringField("Company website", validators=[Optional(), Length(max=255), URL(require_tld=False), no_control_characters])

    # Contact person / account credentials
    contact_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=150), no_control_characters])
    contact_role = StringField("Role at company", validators=[Optional(), Length(max=150), no_control_characters])
    work_email = StringField("Work email", validators=[DataRequired(), Length(max=255), Email(check_deliverability=False), no_control_characters])
    phone = StringField("Phone number", validators=[Optional(), Length(max=30), no_control_characters])
    password = PasswordField("Password", validators=[DataRequired(), password_complexity_check])

    hiring_needs = TextAreaField("What are you hiring for?", validators=[Optional(), Length(max=5000), no_control_characters])

    agree_terms = BooleanField(
        "I confirm I'm authorised to register on behalf of this company, and agree "
        "to the Terms & Conditions and Privacy Policy",
        validators=[DataRequired(message="You must agree to continue.")],
    )
    submit = SubmitField("Submit for review")


class JobPostForm(FlaskForm):
    title = StringField("Job title", validators=[DataRequired(), Length(min=3, max=150), no_control_characters])
    description = TextAreaField("About the role", validators=[DataRequired(), Length(min=10, max=50000), no_control_characters])
    responsibilities = TextAreaField("Responsibilities", validators=[Optional(), Length(max=30000), no_control_characters])
    requirements = TextAreaField("Requirements", validators=[Optional(), Length(max=30000), no_control_characters])

    job_type = SelectField(
        "Job type",
        choices=[
            ("full_time", "Full-time"), ("part_time", "Part-time"),
            ("internship", "Internship"), ("contract", "Contract"),
        ],
    )
    work_mode = SelectField(
        "Work mode",
        choices=[("remote", "Remote"), ("hybrid", "Hybrid"), ("onsite", "On-site")],
    )
    experience_level = SelectField(
        "Experience level",
        choices=[
            ("entry", "Entry level"), ("mid", "Mid level"),
            ("senior", "Senior"), ("lead", "Lead"),
        ],
    )
    location = StringField("Location", validators=[Optional(), Length(max=150), no_control_characters])
    salary_min = StringField("Minimum salary (LPA)", validators=[Optional(), Length(max=50), no_control_characters])
    salary_max = StringField("Maximum salary (LPA)", validators=[Optional(), Length(max=50), no_control_characters])
    status = SelectField(
        "Job status",
        choices=[
            ("active", "Active (Publish immediately)"),
            ("draft", "Draft (Save as draft)"),
            ("paused", "Paused (Hidden temporarily)"),
            ("closed", "Closed (No longer accepting applicants)"),
        ],
        default="active",
    )
    submit = SubmitField("Save Job")
