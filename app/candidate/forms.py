import re
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SubmitField, SelectField, BooleanField
from wtforms.validators import DataRequired, Optional, Length, URL, Regexp, ValidationError


def no_control_characters(form, field):
    """Reject null bytes or control characters in text inputs."""
    if field.data and (re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", field.data)):
        raise ValidationError("Input contains forbidden control characters.")


class ATSCheckForm(FlaskForm):
    resume_name = StringField("Resume name", validators=[Optional(), Length(max=150), no_control_characters])
    target_role = StringField("Target job role", validators=[Optional(), Length(max=150), no_control_characters])
    analysis_mode = StringField("Analysis mode", default="specific_job", validators=[Optional(), Length(max=30), no_control_characters])
    job_selection_type = StringField("Job selection type", default="paste", validators=[Optional(), Length(max=30), no_control_characters])
    selected_job_id = SelectField("Select from platform jobs", choices=[], validators=[Optional()])
    jd_text = TextAreaField("Job description", validators=[Optional(), Length(max=50000), no_control_characters])
    resume_file = FileField(
        "Upload resume", validators=[FileAllowed(["pdf", "doc", "docx"], "PDF or DOCX only.")]
    )
    resume_text = TextAreaField("Or paste resume text", validators=[Optional(), Length(max=50000), no_control_characters])
    submit = SubmitField("Analyze Resume")


class ResumeBuilderForm(FlaskForm):
    resume_name = StringField("Resume name", validators=[Optional(), Length(max=150), no_control_characters])
    target_role = StringField("Target job role", validators=[Optional(), Length(max=150), no_control_characters])
    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=150), no_control_characters])
    title = StringField("Role / title", validators=[Optional(), Length(max=150), no_control_characters])
    email = StringField("Email", validators=[Optional(), Length(max=255), no_control_characters])
    phone = StringField("Phone", validators=[Optional(), Length(max=30), no_control_characters])
    summary = TextAreaField("Summary", validators=[Optional(), Length(max=5000), no_control_characters])
    experience = TextAreaField("Experience", validators=[Optional(), Length(max=20000), no_control_characters])
    education = TextAreaField("Education", validators=[Optional(), Length(max=10000), no_control_characters])
    skills = StringField("Skills (comma separated)", validators=[Optional(), Length(max=1000), no_control_characters])
    submit = SubmitField("Save & download")


class ProfileSettingsForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=150), no_control_characters])
    headline = StringField(
        "Headline", validators=[Optional(), Length(max=150), no_control_characters],
        description="e.g. \"Backend Developer\" or \"Final-year CS student\"",
    )
    phone = StringField("Phone number", validators=[Optional(), Length(max=30), no_control_characters])
    location = StringField("Location", validators=[Optional(), Length(max=150), no_control_characters])
    skills = StringField("Skills (comma separated)", validators=[Optional(), Length(max=500), no_control_characters])
    bio = TextAreaField("About you", validators=[Optional(), Length(max=5000), no_control_characters])
    avatar = FileField("Profile photo", validators=[FileAllowed(["jpg", "jpeg", "png", "webp"], "Use a JPG, PNG, or WEBP image.")])
    experience = TextAreaField("Experience", validators=[Optional(), Length(max=20000), no_control_characters])
    education = TextAreaField("Education", validators=[Optional(), Length(max=10000), no_control_characters])
    certifications = TextAreaField("Certifications", validators=[Optional(), Length(max=10000), no_control_characters])
    projects = TextAreaField("Projects", validators=[Optional(), Length(max=20000), no_control_characters])
    github_url = StringField("GitHub", validators=[Optional(), Length(max=255), URL(require_tld=False), no_control_characters])
    linkedin_url = StringField("LinkedIn", validators=[Optional(), Length(max=255), URL(require_tld=False), no_control_characters])
    portfolio_url = StringField("Portfolio", validators=[Optional(), Length(max=255), URL(require_tld=False), no_control_characters])
    preferred_job_role = StringField("Preferred job role", validators=[Optional(), Length(max=150), no_control_characters])
    preferred_location = StringField("Preferred location", validators=[Optional(), Length(max=150), no_control_characters])
    work_preference = SelectField("Work preference", choices=[("", "Select preference"), ("remote", "Remote"), ("hybrid", "Hybrid"), ("onsite", "On-site")], validators=[Optional()])
    expected_salary = StringField("Expected salary", validators=[Optional(), Length(max=100), no_control_characters])
    experience_level = SelectField("Experience level", choices=[("", "Select level"), ("entry", "Entry level"), ("mid", "Mid level"), ("senior", "Senior"), ("lead", "Lead / manager")], validators=[Optional()])
    submit = SubmitField("Save changes")


class PrivacySettingsForm(FlaskForm):
    public_slug = StringField(
        "Public profile address",
        validators=[
            Optional(),
            Length(min=3, max=80),
            Regexp(r"^[a-z0-9-]+$", message="Use lowercase letters, numbers, and hyphens only."),
            no_control_characters,
        ],
    )
    public_profile_enabled = BooleanField("Make my profile public")
    recruiter_discoverable = BooleanField("Allow approved recruiters to discover me")
    public_resume_enabled = BooleanField("Show my resume content on my public profile")
    submit = SubmitField("Save privacy settings")


class DeleteAccountForm(FlaskForm):
    confirmation = StringField("Type DELETE to confirm", validators=[DataRequired(), Length(max=20), no_control_characters])
    submit = SubmitField("Delete my account permanently")
