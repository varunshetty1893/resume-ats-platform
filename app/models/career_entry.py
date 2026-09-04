from app.utils.time import utcnow

from app import db


class CareerEntry(db.Model):
    """One structured item in a candidate's career profile."""

    __tablename__ = "career_entries"

    TYPE_EXPERIENCE = "experience"
    TYPE_EDUCATION = "education"
    TYPE_CERTIFICATION = "certification"
    TYPE_PROJECT = "project"
    TYPES = (TYPE_EXPERIENCE, TYPE_EDUCATION, TYPE_CERTIFICATION, TYPE_PROJECT)

    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    entry_type = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    organization = db.Column(db.String(200), nullable=True)
    location = db.Column(db.String(150), nullable=True)
    start_date = db.Column(db.String(50), nullable=True)
    end_date = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    credential_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    candidate = db.relationship("User", back_populates="career_entries")

    def __repr__(self):
        return f"<CareerEntry {self.entry_type}:{self.title}>"
