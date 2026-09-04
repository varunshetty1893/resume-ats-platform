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
        "Upload resume", validators=[FileAllowed(["pdf", "docx"], "PDF or DOCX only.")]
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


def valid_text_content(form, field):
    """Ensure text is not just keyboard mash or repeated characters."""
    if field.data:
        val = field.data.strip()
        if re.match(r"^(.)\1{4,}$", val):
            raise ValidationError("Please provide meaningful text.")


def valid_phone_number(form, field):
    """Ensure phone number has realistic digit count and format."""
    if field.data:
        digits = re.sub(r"\D", "", field.data)
        if len(digits) < 7 or len(digits) > 16:
            raise ValidationError("Please enter a valid phone number (7 to 15 digits).")


class ProfileSettingsForm(FlaskForm):
    full_name = StringField(
        "Full name",
        validators=[
            DataRequired(message="Full name is required."),
            Length(min=2, max=100, message="Full name must be between 2 and 100 characters."),
            valid_text_content,
            no_control_characters,
        ],
    )
    headline = StringField(
        "Headline",
        validators=[
            Optional(),
            Length(max=150, message="Headline cannot exceed 150 characters."),
            valid_text_content,
            no_control_characters,
        ],
        description="e.g. \"Backend Developer\" or \"Final-year CS student\"",
    )
    phone = StringField(
        "Phone number",
        validators=[
            DataRequired(message="Phone number is required."),
            Length(min=7, max=30, message="Phone number must be between 7 and 30 characters."),
            valid_phone_number,
            no_control_characters,
        ],
    )
    location = StringField(
        "Location",
        validators=[
            DataRequired(message="Location is required."),
            Length(min=2, max=150, message="Location must be between 2 and 150 characters."),
            valid_text_content,
            no_control_characters,
        ],
    )
    skills = StringField(
        "Skills (comma separated)",
        validators=[
            DataRequired(message="Please provide at least one skill."),
            Length(min=2, max=500, message="Skills must be between 2 and 500 characters."),
            valid_text_content,
            no_control_characters,
        ],
    )
    bio = TextAreaField(
        "About you",
        validators=[
            DataRequired(message="About you is required."),
            Length(min=10, max=5000, message="About you must be at least 10 characters long."),
            valid_text_content,
            no_control_characters,
        ],
    )
    avatar = FileField(
        "Profile photo",
        validators=[FileAllowed(["jpg", "jpeg", "png", "webp"], "Use a JPG, PNG, or WEBP image.")],
    )
    experience = TextAreaField("Experience", validators=[Optional(), Length(max=20000), no_control_characters])
    education = TextAreaField("Education", validators=[Optional(), Length(max=10000), no_control_characters])
    certifications = TextAreaField("Certifications", validators=[Optional(), Length(max=10000), no_control_characters])
    projects = TextAreaField("Projects", validators=[Optional(), Length(max=20000), no_control_characters])
    github_url = StringField(
        "GitHub",
        validators=[
            Optional(),
            Length(max=255),
            URL(require_tld=False, message="Please enter a valid GitHub URL (e.g. https://github.com/your-name)."),
            no_control_characters,
        ],
    )
    linkedin_url = StringField(
        "Other public profile / Social media",
        validators=[
            Optional(),
            Length(max=255),
            URL(require_tld=False, message="Please enter a valid URL (e.g. https://x.com/your-handle)."),
            no_control_characters,
        ],
    )
    portfolio_url = StringField(
        "Portfolio",
        validators=[
            Optional(),
            Length(max=255),
            URL(require_tld=False, message="Please enter a valid portfolio URL (e.g. https://yourportfolio.com)."),
            no_control_characters,
        ],
    )
    preferred_job_role = StringField(
        "Preferred job role",
        validators=[Optional(), Length(max=150), valid_text_content, no_control_characters],
    )
    preferred_location = StringField(
        "Preferred location",
        validators=[Optional(), Length(max=150), valid_text_content, no_control_characters],
    )
    work_preference = SelectField(
        "Work preference",
        choices=[("", "Select preference"), ("remote", "Remote"), ("hybrid", "Hybrid"), ("onsite", "On-site")],
        validators=[DataRequired(message="Please select your work preference.")],
    )
    expected_salary = StringField(
        "Expected salary",
        validators=[Optional(), Length(max=100), valid_text_content, no_control_characters],
    )
    experience_level = SelectField(
        "Experience level",
        choices=[("", "Select level"), ("entry", "Entry level"), ("mid", "Mid level"), ("senior", "Senior"), ("lead", "Lead / manager")],
        validators=[DataRequired(message="Please select your experience level.")],
    )
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
