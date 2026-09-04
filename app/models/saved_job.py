from app.utils.time import utcnow

from app import db


class SavedJob(db.Model):
    __tablename__ = "saved_jobs"

    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    candidate = db.relationship("User", back_populates="saved_jobs")
    job = db.relationship("Job")

    __table_args__ = (db.UniqueConstraint("candidate_id", "job_id", name="uq_saved_job"),)
