from datetime import datetime

from app import db


class Job(db.Model):
    """A job posting created by an approved recruiter."""

    __tablename__ = "jobs"

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_CLOSED = "closed"
    STATUSES = (STATUS_DRAFT, STATUS_ACTIVE, STATUS_PAUSED, STATUS_CLOSED)

    id = db.Column(db.Integer, primary_key=True)
    recruiter_profile_id = db.Column(
        db.Integer, db.ForeignKey("recruiter_profiles.id"), nullable=False
    )

    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    responsibilities = db.Column(db.Text, nullable=True)
    requirements = db.Column(db.Text, nullable=True)

    job_type = db.Column(db.String(30), nullable=False, default="full_time")
    work_mode = db.Column(db.String(20), nullable=False, default="remote")  # remote/hybrid/onsite
    experience_level = db.Column(db.String(20), nullable=False, default="mid")
    location = db.Column(db.String(150), nullable=True)

    salary_min = db.Column(db.Integer, nullable=True)
    salary_max = db.Column(db.Integer, nullable=True)

    status = db.Column(db.String(20), nullable=False, default=STATUS_ACTIVE)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    recruiter_profile = db.relationship("RecruiterProfile", back_populates="jobs")
    applications = db.relationship("Application", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Job {self.title}>"
