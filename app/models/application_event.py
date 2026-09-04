from app.utils.time import utcnow

from app import db


class ApplicationEvent(db.Model):
    __tablename__ = "application_events"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False)
    status = db.Column(db.String(30), nullable=False)
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    application = db.relationship("Application", back_populates="events")
