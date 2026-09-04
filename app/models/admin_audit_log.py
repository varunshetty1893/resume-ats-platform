from app.utils.time import utcnow

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
    ACTION_PASSWORD_CHANGE = "password_change"
    ACTION_SECURITY_ALERT = "security_alert"
    ACTION_EXPORT_REPORT = "export_report"
    ACTION_SYSTEM_CONFIG = "system_config_change"
    ACTION_RECRUITER_VETTING = "recruiter_vetting_review"
    ACTION_JOB_MODERATION = "job_moderation"
    ACTION_USER_ROLE_CHANGE = "user_role_change"
    ACTION_PURGE_CACHE = "purge_cache"
    ACTION_ATS_POLICY_UPDATE = "ats_policy_update"
    ACTION_PLATFORM_BACKUP = "platform_backup"
    ACTION_BACKFILL_MATCH_SCORES = "backfill_match_scores"

    ENTITY_USER = "user"
    ENTITY_RECRUITER = "recruiter"
    ENTITY_JOB = "job"
    ENTITY_APPLICATION = "application"
    ENTITY_SETTING = "setting"
    ENTITY_SYSTEM = "system"
    ENTITY_SECURITY = "security"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    action = db.Column(db.String(60), nullable=False)
    entity_type = db.Column(db.String(30), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    detail = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    admin = db.relationship("User", foreign_keys=[admin_id])

    def __repr__(self):
        return f"<AdminAuditLog admin={self.admin_id} action={self.action}>"
