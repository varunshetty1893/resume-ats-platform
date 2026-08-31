from datetime import datetime

from app import db


class Resume(db.Model):
    """A candidate's resume — either an uploaded file or pasted text."""

    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    source = db.Column(db.String(10), nullable=False, default="paste")  # 'upload' | 'paste' | 'builder'
    original_filename = db.Column(db.String(255), nullable=True)
    stored_filename = db.Column(db.String(255), nullable=True)  # path on disk, if uploaded
    raw_text = db.Column(db.Text, nullable=False)  # extracted/pasted plain text
    name = db.Column(db.String(150), nullable=True)
    target_role = db.Column(db.String(150), nullable=True)

    # Latest ATS check result against a JD, if any
    last_ats_score = db.Column(db.Float, nullable=True)
    last_matched_keywords = db.Column(db.Text, nullable=True)  # comma-separated
    last_missing_keywords = db.Column(db.Text, nullable=True)  # comma-separated

    is_primary = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    candidate = db.relationship("User", back_populates="resumes", foreign_keys=[candidate_id])
    applications = db.relationship("Application", back_populates="resume")

    def __repr__(self):
        return f"<Resume {self.id} candidate={self.candidate_id}>"
