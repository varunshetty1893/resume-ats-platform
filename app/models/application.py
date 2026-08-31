from datetime import datetime

from app import db


class Application(db.Model):
    """A candidate's application to a job, with a computed match score."""

    __tablename__ = "applications"

    STATUS_APPLIED = "applied"
    STATUS_UNDER_REVIEW = "under_review"
    STATUS_SHORTLISTED = "shortlisted"
    STATUS_REJECTED = "rejected"
    STATUS_HIRED = "hired"
    STATUS_INTERVIEW = "interview"
    STATUSES = (
        STATUS_APPLIED, STATUS_UNDER_REVIEW, STATUS_SHORTLISTED,
        STATUS_REJECTED, STATUS_HIRED, STATUS_INTERVIEW,
    )

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False)

    match_score = db.Column(db.Float, nullable=True)
    cover_note = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_APPLIED)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)

    job = db.relationship("Job", back_populates="applications")
    candidate = db.relationship("User", back_populates="applications", foreign_keys=[candidate_id])
    resume = db.relationship("Resume", back_populates="applications")
    events = db.relationship("ApplicationEvent", back_populates="application", cascade="all, delete-orphan", order_by="ApplicationEvent.created_at.asc()")

    __table_args__ = (
        db.UniqueConstraint("job_id", "candidate_id", name="uq_one_application_per_job"),
    )

    def __repr__(self):
        return f"<Application job={self.job_id} candidate={self.candidate_id}>"
