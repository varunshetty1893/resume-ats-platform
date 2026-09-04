import re
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, ValidationError
from app.models.support_ticket import SupportTicket


def no_control_characters(form, field):
    """Reject null bytes or control characters in text inputs."""
    if field.data and (re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", field.data)):
        raise ValidationError("Input contains forbidden control characters.")


class SupportTicketForm(FlaskForm):
    """Form for creating a new support ticket."""

    issue_type = SelectField(
        "Issue Category",
        choices=[
            (SupportTicket.ISSUE_ACCOUNT, "Account & Login"),
            (SupportTicket.ISSUE_RESUME_ATS, "Resume & ATS Checker"),
            (SupportTicket.ISSUE_JOB_POSTING, "Jobs & Applications"),
            (SupportTicket.ISSUE_RECRUITER_HIRING, "Recruiter & Hiring"),
            (SupportTicket.ISSUE_TECHNICAL, "Technical Issue / Bug"),
            (SupportTicket.ISSUE_BILLING, "Billing & Subscription"),
            (SupportTicket.ISSUE_OTHER, "General Inquiry"),
        ],
        validators=[DataRequired(message="Please select an issue category.")],
        default=SupportTicket.ISSUE_OTHER,
    )

    subject = StringField(
        "Subject",
        validators=[
            DataRequired(message="Please enter a subject line."),
            Length(min=4, max=200, message="Subject must be between 4 and 200 characters."),
            no_control_characters,
        ],
    )

    description = TextAreaField(
        "Describe your issue",
        validators=[
            DataRequired(message="Please provide details about your issue."),
            Length(min=10, max=10000, message="Description must be between 10 and 10,000 characters."),
            no_control_characters,
        ],
    )

    attachment = FileField(
        "Attachment (optional)",
        validators=[
            Optional(),
            FileAllowed(["pdf", "png", "jpg", "jpeg", "docx", "doc", "txt", "webp"], "Allowed file types: PDF, PNG, JPG, JPEG, DOCX, DOC, TXT, WEBP"),
        ],
    )

    submit = SubmitField("Submit Ticket")


class SupportReplyForm(FlaskForm):
    """Form for adding a reply message to an existing ticket."""

    message = TextAreaField(
        "Reply Message",
        validators=[
            DataRequired(message="Please enter a message."),
            Length(min=2, max=10000, message="Message must be between 2 and 10,000 characters."),
            no_control_characters,
        ],
    )

    attachment = FileField(
        "Attachment (optional)",
        validators=[
            Optional(),
            FileAllowed(["pdf", "png", "jpg", "jpeg", "docx", "doc", "txt", "webp"], "Allowed file types: PDF, PNG, JPG, JPEG, DOCX, DOC, TXT, WEBP"),
        ],
    )

    submit = SubmitField("Send Reply")
