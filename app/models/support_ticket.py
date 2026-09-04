from app.utils.time import utcnow
from app import db


class SupportTicket(db.Model):
    """A customer support ticket submitted by a candidate or recruiter."""

    __tablename__ = "support_tickets"

    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_RESOLVED = "resolved"
    STATUSES = (STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_RESOLVED)

    ISSUE_ACCOUNT = "account"
    ISSUE_RESUME_ATS = "resume_ats"
    ISSUE_JOB_POSTING = "job_posting"
    ISSUE_RECRUITER_HIRING = "recruiter_hiring"
    ISSUE_TECHNICAL = "technical"
    ISSUE_BILLING = "billing"
    ISSUE_OTHER = "other"

    ISSUE_TYPE_LABELS = {
        ISSUE_ACCOUNT: "Account & Login",
        ISSUE_RESUME_ATS: "Resume & ATS Checker",
        ISSUE_JOB_POSTING: "Jobs & Applications",
        ISSUE_RECRUITER_HIRING: "Recruiter & Hiring",
        ISSUE_TECHNICAL: "Technical Issue / Bug",
        ISSUE_BILLING: "Billing & Subscription",
        ISSUE_OTHER: "General Inquiry",
    }

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    issue_type = db.Column(db.String(50), nullable=False, default=ISSUE_OTHER)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    attachment_filename = db.Column(db.String(255), nullable=True)

    status = db.Column(db.String(20), nullable=False, default=STATUS_OPEN, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    user = db.relationship("User", back_populates="support_tickets")
    messages = db.relationship(
        "SupportTicketMessage",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="SupportTicketMessage.created_at.asc()",
    )

    @property
    def issue_type_label(self):
        return self.ISSUE_TYPE_LABELS.get(self.issue_type, self.issue_type.replace("_", " ").capitalize())

    @property
    def status_label(self):
        return self.status.replace("_", " ").capitalize()

    def __repr__(self):
        return f"<SupportTicket #{self.id} user_id={self.user_id} status={self.status}>"


class SupportTicketMessage(db.Model):
    """Threaded message / response attached to a support ticket."""

    __tablename__ = "support_ticket_messages"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("support_tickets.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    message = db.Column(db.Text, nullable=False)
    attachment_filename = db.Column(db.String(255), nullable=True)
    is_admin_response = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    ticket = db.relationship("SupportTicket", back_populates="messages")
    sender = db.relationship("User")

    def __repr__(self):
        return f"<SupportTicketMessage #{self.id} ticket_id={self.ticket_id} admin={self.is_admin_response}>"
