from app.utils.time import utcnow

from app import db


class AdminSetting(db.Model):
    """Platform-wide key/value settings managed by admins.

    Keys are unique strings (e.g. 'registration_open', 'ats_enabled').
    Values are stored as text and interpreted by the application.
    """

    __tablename__ = "admin_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    label = db.Column(db.String(150), nullable=True)
    description = db.Column(db.String(300), nullable=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    updated_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    updated_by = db.relationship("User", foreign_keys=[updated_by_admin_id])

    @classmethod
    def get(cls, key, default=None):
        """Return the value for a setting key, or default if not found."""
        row = cls.query.filter_by(key=key).first()
        return row.value if row else default

    @classmethod
    def set(cls, key, value, admin_id=None):
        """Upsert a setting value."""
        row = cls.query.filter_by(key=key).first()
        if row:
            row.value = value
            row.updated_at = utcnow()
            if admin_id:
                row.updated_by_admin_id = admin_id
        else:
            row = cls(key=key, value=value, updated_by_admin_id=admin_id)
            db.session.add(row)
        return row

    def __repr__(self):
        return f"<AdminSetting {self.key}={self.value!r}>"
