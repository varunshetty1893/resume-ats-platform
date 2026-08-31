from datetime import datetime

from app import db


class Notification(db.Model):
    """Notification model for all user roles (candidates, recruiters, admins)."""
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    # The foreign key references users.id (named candidate_id for backwards DB compatibility)
    candidate_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    link = db.Column(db.String(300), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    candidate = db.relationship("User", back_populates="notifications")

    def __init__(self, *args, **kwargs):
        # Support user_id as an alias for candidate_id
        if "user_id" in kwargs and "candidate_id" not in kwargs:
            kwargs["candidate_id"] = kwargs.pop("user_id")
        super().__init__(*args, **kwargs)

    @property
    def user_id(self):
        return self.candidate_id

    @user_id.setter
    def user_id(self, val):
        self.candidate_id = val

    @property
    def user(self):
        return self.candidate

    @user.setter
    def user(self, val):
        self.candidate = val

    def __repr__(self):
        return f"<Notification user_id={self.candidate_id} title='{self.title}'>"
