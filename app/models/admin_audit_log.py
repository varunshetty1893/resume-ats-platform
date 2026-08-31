from datetime import datetime

from app import db


class AdminAuditLog(db.Model):
    """Records every important administrative action taken on the platform.

    Each row tracks who did what, against which entity, and when.
    """

    __tablename__ = "admin_audit_logs"

    ACTION_APPROVE_RECRUITER = "approve_recruiter"
    ACTION_REJECT_RECRUITER = "reject_recruiter"
    ACTION_ENABLE_USER = "enable_user"
    ACTION_DISABLE_USER = "disable_user"
    ACTION_UPDATE_JOB_STATUS = "update_job_status"
    ACTION_UPDATE_SETTING = "update_setting"
    ACTION_UPDATE_PROFILE = "update_profile"

    ENTITY_USER = "user"
    ENTITY_RECRUITER = "recruiter"
    ENTITY_JOB = "job"
    ENTITY_APPLICATION = "application"
    ENTITY_SETTING = "setting"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    action = db.Column(db.String(60), nullable=False)
    entity_type = db.Column(db.String(30), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    detail = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    admin = db.relationship("User", foreign_keys=[admin_id])

    def __repr__(self):
        return f"<AdminAuditLog admin={self.admin_id} action={self.action}>"
