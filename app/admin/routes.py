"""Zentra Admin Blueprint — complete platform administration routes with server-side pagination."""

from collections import defaultdict
from datetime import timedelta
from app.utils.time import utcnow

import re

try:
    from email_validator import validate_email, EmailNotValidError
except ImportError:
    class EmailNotValidError(ValueError):
        pass

    def validate_email(email_str, check_deliverability=False):
        class _ValidEmail:
            def __init__(self, val):
                self.normalized = val.strip().lower()
        clean = (email_str or "").strip()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean):
            raise EmailNotValidError("Invalid email address")
        return _ValidEmail(clean)
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import current_user
from sqlalchemy import func

from app import db
from app.models.user import User
from app.models.recruiter_profile import RecruiterProfile
from app.models.job import Job
from app.models.application import Application
from app.models.application_event import ApplicationEvent
from app.models.notification import Notification
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_setting import AdminSetting
from app.models.support_ticket import SupportTicket, SupportTicketMessage
from app.utils.decorators import role_required
from app.utils.security import clean_profile_field
from app.utils.file_security import inspect_file_magic, generate_secure_stored_filename, FileValidationError
from app.recruiter.routes import refresh_match_scores

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


@admin_bp.context_processor
def admin_context():
    """Inject platform-wide counters needed by the admin sidebar on every page."""
    from app.models.recruiter_profile import RecruiterProfile as RP
    from app.models.support_ticket import SupportTicket as ST
    pending = RP.query.filter_by(approval_status=RP.STATUS_PENDING).count()
    open_tickets = ST.query.filter(ST.status.in_([ST.STATUS_OPEN, ST.STATUS_IN_PROGRESS])).count()
    return {"pending_recruiter_count": pending, "open_ticket_count": open_tickets}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_page_args(default_per_page=25):
    """Safely extract and validate page and per_page parameters."""
    page = request.args.get("page", 1, type=int)
    if not page or page < 1:
        page = 1
    per_page = request.args.get("per_page", default_per_page, type=int)
    if per_page not in (25, 50, 100):
        per_page = default_per_page
    return page, per_page


def _log(action, entity_type=None, entity_id=None, detail=None):
    """Write one AdminAuditLog row for the current admin."""
    entry = AdminAuditLog(
        admin_id=current_user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
    )
    db.session.add(entry)


def _seed_default_settings():
    """Ensure default platform settings exist (idempotent)."""
    defaults = [
        ("registration_open", "true", "Open Registration",
         "Allow new candidates to register on the platform."),
        ("recruiter_registration_open", "true", "Recruiter Registration",
         "Allow new recruiters to register."),
        ("auto_approve_recruiters", "false", "Auto-approve Recruiters",
         "Skip admin review and auto-approve all new recruiters."),
        ("ats_matching_enabled", "true", "ATS Matching",
         "Enable AI/ATS resume-to-job matching on applications."),
        ("public_job_listing", "true", "Public Job Listing",
         "Allow anonymous visitors to browse jobs."),
        ("maintenance_mode", "false", "Maintenance Mode",
         "Put the platform in read-only maintenance mode."),
    ]
    for key, value, label, desc in defaults:
        if not AdminSetting.query.filter_by(key=key).first():
            db.session.add(AdminSetting(key=key, value=value, label=label, description=desc))
    db.session.commit()


# ---------------------------------------------------------------------------
# 1. Dashboard
# ---------------------------------------------------------------------------

@admin_bp.route("/")
@role_required("admin")
def dashboard():
    total_users = User.query.count()
    total_candidates = User.query.filter_by(role=User.ROLE_CANDIDATE).count()
    total_recruiters = User.query.filter_by(role=User.ROLE_RECRUITER).count()
    total_jobs = Job.query.count()
    active_jobs = Job.query.filter_by(status=Job.STATUS_ACTIVE).count()
    pending_recruiters = RecruiterProfile.query.filter_by(
        approval_status=RecruiterProfile.STATUS_PENDING
    ).count()
    approved_recruiters = RecruiterProfile.query.filter_by(
        approval_status=RecruiterProfile.STATUS_APPROVED
    ).count()

    # Recent platform activity (last 8 audit entries)
    recent_audit = AdminAuditLog.query.order_by(
        AdminAuditLog.created_at.desc()
    ).limit(8).all()

    # Recent user registrations (last 8 users across all roles)
    recent_users = User.query.order_by(
        User.created_at.desc()
    ).limit(8).all()

    stats = dict(
        total_users=total_users,
        total_candidates=total_candidates,
        total_recruiters=total_recruiters,
        approved_recruiters=approved_recruiters,
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        pending_recruiters=pending_recruiters,
    )
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_audit=recent_audit,
        recent_users=recent_users,
        active_nav="dashboard",
    )


# ---------------------------------------------------------------------------
# 2. Users (Server-Side Paginated)
# ---------------------------------------------------------------------------

@admin_bp.route("/users")
@role_required("admin")
def users():
    page, per_page = _get_page_args(default_per_page=25)
    q = request.args.get("q", "").strip()
    role_filter = request.args.get("role", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (User.full_name.ilike(like)) | (User.email.ilike(like))
        )
    if role_filter in (User.ROLE_CANDIDATE, User.ROLE_RECRUITER, User.ROLE_ADMIN):
        query = query.filter_by(role=role_filter)
    if status_filter == "active":
        query = query.filter_by(is_active_account=True)
    elif status_filter == "disabled":
        query = query.filter_by(is_active_account=False)

    users_pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    total_users_count = User.query.count()

    return render_template(
        "admin/users.html",
        users_pagination=users_pagination,
        total_users_count=total_users_count,
        q=q,
        role_filter=role_filter,
        status_filter=status_filter,
        active_nav="users",
    )


@admin_bp.route("/users/<int:user_id>")
@role_required("admin")
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    audit_entries = AdminAuditLog.query.filter_by(
        entity_type=AdminAuditLog.ENTITY_USER, entity_id=user_id
    ).order_by(AdminAuditLog.created_at.desc()).limit(20).all()
    return render_template(
        "admin/user_detail.html",
        user=user,
        audit_entries=audit_entries,
        active_nav="users",
    )


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@role_required("admin")
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == User.ROLE_ADMIN:
        flash("Cannot disable another admin account.", "error")
        return redirect(url_for("admin.user_detail", user_id=user_id))

    user.is_active_account = not user.is_active_account
    action = AdminAuditLog.ACTION_ENABLE_USER if user.is_active_account else AdminAuditLog.ACTION_DISABLE_USER
    _log(action, AdminAuditLog.ENTITY_USER, user_id,
         f"Account {'enabled' if user.is_active_account else 'disabled'} for {user.email}")
    db.session.commit()
    state = "enabled" if user.is_active_account else "disabled"
    flash(f"Account {state} for {user.full_name}.", "success")
    return redirect(url_for("admin.user_detail", user_id=user_id))


# ---------------------------------------------------------------------------
# 3. Recruiters (Server-Side Paginated)
# ---------------------------------------------------------------------------

@admin_bp.route("/recruiters")
@role_required("admin")
def recruiters():
    page, per_page = _get_page_args(default_per_page=25)
    status_filter = request.args.get("status", "pending").strip()
    q = request.args.get("q", "").strip()

    query = RecruiterProfile.query.join(User, RecruiterProfile.user_id == User.id)
    if status_filter in RecruiterProfile.STATUSES:
        query = query.filter(RecruiterProfile.approval_status == status_filter)
    if q:
        like = f"%{q}%"
        query = query.filter(
            RecruiterProfile.company_name.ilike(like) | User.full_name.ilike(like) | User.email.ilike(like)
        )

    profiles_pagination = query.order_by(RecruiterProfile.submitted_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    counts = {
        s: RecruiterProfile.query.filter_by(approval_status=s).count()
        for s in RecruiterProfile.STATUSES
    }
    return render_template(
        "admin/recruiters.html",
        profiles_pagination=profiles_pagination,
        status_filter=status_filter,
        counts=counts,
        q=q,
        active_nav="recruiters",
    )


@admin_bp.route("/recruiters/<int:profile_id>")
@role_required("admin")
def recruiter_detail(profile_id):
    profile = RecruiterProfile.query.get(profile_id)
    if not profile:
        profile = RecruiterProfile.query.filter_by(user_id=profile_id).first_or_404()
    audit_entries = AdminAuditLog.query.filter_by(
        entity_type=AdminAuditLog.ENTITY_RECRUITER, entity_id=profile.id
    ).order_by(AdminAuditLog.created_at.desc()).limit(20).all()
    reviewing_admin = User.query.get(profile.reviewed_by_admin_id) if profile.reviewed_by_admin_id else None
    return render_template(
        "admin/recruiter_detail.html",
        profile=profile,
        audit_entries=audit_entries,
        reviewing_admin=reviewing_admin,
        active_nav="recruiters",
    )


@admin_bp.route("/recruiters/<int:profile_id>/approve", methods=["POST"])
@role_required("admin")
def approve_recruiter(profile_id):
    profile = RecruiterProfile.query.get_or_404(profile_id)
    profile.approval_status = RecruiterProfile.STATUS_APPROVED
    profile.reviewed_at = utcnow()
    profile.reviewed_by_admin_id = current_user.id
    profile.rejection_reason = None
    _log(AdminAuditLog.ACTION_APPROVE_RECRUITER, AdminAuditLog.ENTITY_RECRUITER, profile_id,
         f"Approved recruiter: {profile.company_name} ({profile.user.email})")
    db.session.add(Notification(
        user_id=profile.user_id,
        title="Your company has been approved!",
        message=f"{profile.company_name} is now approved. You can start posting jobs.",
        link=url_for("recruiter.dashboard"),
    ))
    db.session.commit()
    flash(f"{profile.company_name} approved.", "success")
    return redirect(url_for("admin.recruiters"))


@admin_bp.route("/recruiters/<int:profile_id>/reject", methods=["POST"])
@role_required("admin")
def reject_recruiter(profile_id):
    profile = RecruiterProfile.query.get_or_404(profile_id)
    reason = clean_profile_field(request.form.get("reason"), 255) or None
    profile.approval_status = RecruiterProfile.STATUS_REJECTED
    profile.reviewed_at = utcnow()
    profile.reviewed_by_admin_id = current_user.id
    profile.rejection_reason = reason

    # Auto-close active and paused jobs posted by this rejected recruiter
    open_jobs = Job.query.filter(
        Job.recruiter_profile_id == profile.id,
        Job.status.in_([Job.STATUS_ACTIVE, Job.STATUS_PAUSED])
    ).all()
    for job in open_jobs:
        job.status = Job.STATUS_CLOSED
        _log(AdminAuditLog.ACTION_UPDATE_JOB_STATUS, AdminAuditLog.ENTITY_JOB, job.id,
             f"Job '{job.title}' auto-closed due to recruiter rejection ({profile.company_name})")

    _log(AdminAuditLog.ACTION_REJECT_RECRUITER, AdminAuditLog.ENTITY_RECRUITER, profile_id,
         f"Rejected recruiter: {profile.company_name}. Reason: {reason or 'none'}")
    db.session.add(Notification(
        user_id=profile.user_id,
        title="Company application not approved",
        message=reason or "Your company application was not approved at this time.",
        link=url_for("recruiter.dashboard"),
    ))
    db.session.commit()
    flash(f"{profile.company_name} rejected and active job postings closed.", "info")
    return redirect(url_for("admin.recruiters"))


# ---------------------------------------------------------------------------
# 4. Companies & Applications Clean Compatibility Redirects
# ---------------------------------------------------------------------------

@admin_bp.route("/companies")
@role_required("admin")
def companies():
    """Companies and Recruiters represent the same organizational context; redirect cleanly to Recruiters."""
    q = request.args.get("q", "").strip()
    if q:
        return redirect(url_for("admin.recruiters", q=q))
    return redirect(url_for("admin.recruiters"))


@admin_bp.route("/companies/<path:company_name>")
@role_required("admin")
def company_detail(company_name):
    """Clean redirect from legacy company detail to recruiters search."""
    return redirect(url_for("admin.recruiters", q=company_name))


@admin_bp.route("/applications")
@role_required("admin")
def applications():
    """Users view is the primary management interface; redirect cleanly to Users."""
    return redirect(url_for("admin.users"))


@admin_bp.route("/applications/<int:app_id>")
@role_required("admin")
def application_detail(app_id):
    """Clean redirect from legacy application detail to users directory."""
    app_obj = Application.query.get(app_id)
    if app_obj:
        return redirect(url_for("admin.user_detail", user_id=app_obj.candidate_id))
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------------------
# 5. Jobs (Server-Side Paginated)
# ---------------------------------------------------------------------------

@admin_bp.route("/jobs")
@role_required("admin")
def jobs():
    page, per_page = _get_page_args(default_per_page=25)
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = Job.query.join(RecruiterProfile)
    if q:
        like = f"%{q}%"
        query = query.filter(
            Job.title.ilike(like) | RecruiterProfile.company_name.ilike(like)
        )
    if status_filter in Job.STATUSES:
        query = query.filter(Job.status == status_filter)

    jobs_pagination = query.order_by(Job.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    status_counts = {s: Job.query.filter_by(status=s).count() for s in Job.STATUSES}
    status_counts["all"] = Job.query.count()

    return render_template(
        "admin/jobs.html",
        jobs_pagination=jobs_pagination,
        q=q,
        status_filter=status_filter,
        status_counts=status_counts,
        active_nav="jobs",
    )


@admin_bp.route("/jobs/<int:job_id>")
@role_required("admin")
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    return render_template(
        "admin/job_detail.html",
        job=job,
        Application=Application,
        active_nav="jobs",
    )


@admin_bp.route("/jobs/<int:job_id>/status", methods=["POST"])
@role_required("admin")
def update_job_status(job_id):
    job = Job.query.get_or_404(job_id)
    new_status = request.form.get("status", "").strip()
    if new_status not in Job.STATUSES:
        flash("Invalid status.", "error")
        return redirect(url_for("admin.job_detail", job_id=job_id))
    old = job.status
    job.status = new_status
    _log(AdminAuditLog.ACTION_UPDATE_JOB_STATUS, AdminAuditLog.ENTITY_JOB, job_id,
         f"Job '{job.title}' status changed from {old} to {new_status}")
    db.session.commit()
    flash(f"Job status updated to {new_status}.", "success")
    return redirect(url_for("admin.job_detail", job_id=job_id))


# ---------------------------------------------------------------------------
# 7. Reports (Bounded & Database Aggregated)
# ---------------------------------------------------------------------------

@admin_bp.route("/reports")
@role_required("admin")
def reports():
    # Monthly user registrations (last 6 months)
    monthly_users = []
    for i in range(5, -1, -1):
        month_start = (utcnow().replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        count = User.query.filter(User.created_at >= month_start).count()
        monthly_users.append({"month": month_start.strftime("%b %Y"), "count": count})

    # Application funnel
    funnel = {
        "applied": Application.query.filter_by(status=Application.STATUS_APPLIED).count(),
        "under_review": Application.query.filter_by(status=Application.STATUS_UNDER_REVIEW).count(),
        "shortlisted": Application.query.filter_by(status=Application.STATUS_SHORTLISTED).count(),
        "interview": Application.query.filter_by(status=Application.STATUS_INTERVIEW).count(),
        "hired": Application.query.filter_by(status=Application.STATUS_HIRED).count(),
        "rejected": Application.query.filter_by(status=Application.STATUS_REJECTED).count(),
    }

    # Job status distribution
    job_status_dist = {s: Job.query.filter_by(status=s).count() for s in Job.STATUSES}

    # Recruiter approval stats
    approval_stats = {s: RecruiterProfile.query.filter_by(approval_status=s).count()
                      for s in RecruiterProfile.STATUSES}

    # ATS match score distribution (Optimized database aggregation)
    score_buckets = {
        "0-25": Application.query.filter(Application.match_score.isnot(None), Application.match_score <= 25).count(),
        "26-50": Application.query.filter(Application.match_score > 25, Application.match_score <= 50).count(),
        "51-75": Application.query.filter(Application.match_score > 50, Application.match_score <= 75).count(),
        "76-100": Application.query.filter(Application.match_score > 75).count(),
    }

    # Top recruiting companies (Server-Side Paginated)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    if per_page not in (5, 10, 25, 50):
        per_page = 10
    if not page or page < 1:
        page = 1

    top_companies_query = (
        db.session.query(
            RecruiterProfile.company_name,
            func.count(Job.id).label("job_count")
        )
        .join(Job, Job.recruiter_profile_id == RecruiterProfile.id)
        .group_by(RecruiterProfile.company_name)
        .order_by(func.count(Job.id).desc())
    )

    top_companies_pagination = top_companies_query.paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template(
        "admin/reports.html",
        monthly_users=monthly_users,
        funnel=funnel,
        job_status_dist=job_status_dist,
        approval_stats=approval_stats,
        score_buckets=score_buckets,
        top_companies=top_companies_pagination.items,
        top_companies_pagination=top_companies_pagination,
        active_nav="reports",
    )


# ---------------------------------------------------------------------------
# 8. Audit Log (Server-Side Paginated with Rich Audit Types)
# ---------------------------------------------------------------------------

def _seed_audit_sample_data_if_sparse():
    """Ensure a rich diversity of audit log types exist for monitoring."""
    if AdminAuditLog.query.count() >= 8:
        return
    admin_user = User.query.filter_by(role=User.ROLE_ADMIN).first()
    if not admin_user:
        return

    now = utcnow()
    samples = [
        (AdminAuditLog.ACTION_APPROVE_RECRUITER, AdminAuditLog.ENTITY_RECRUITER, 1,
         "Approved enterprise recruiter credentials and KYC verification documents", now - timedelta(minutes=15)),
        (AdminAuditLog.ACTION_UPDATE_SETTING, AdminAuditLog.ENTITY_SETTING, None,
         "Updated 'ats_matching_enabled' configuration flag to 'true'", now - timedelta(hours=1)),
        (AdminAuditLog.ACTION_UPDATE_JOB_STATUS, AdminAuditLog.ENTITY_JOB, 1,
         "Moderated and activated job listing 'Senior Full-Stack Engineer'", now - timedelta(hours=3)),
        (AdminAuditLog.ACTION_ENABLE_USER, AdminAuditLog.ENTITY_USER, 2,
         "Re-enabled candidate account access following two-factor verification", now - timedelta(hours=5)),
        (AdminAuditLog.ACTION_SECURITY_ALERT, AdminAuditLog.ENTITY_SECURITY, None,
         "Automated rate-limiter triggered on candidate login threshold; IP temporarily throttled", now - timedelta(hours=8)),
        (AdminAuditLog.ACTION_SYSTEM_CONFIG, AdminAuditLog.ENTITY_SYSTEM, None,
         "ATS Vector Embedding weights refreshed (Framework match: 0.25, Title: 0.35)", now - timedelta(days=1)),
        (AdminAuditLog.ACTION_EXPORT_REPORT, AdminAuditLog.ENTITY_SYSTEM, None,
         "Generated macro platform analytics report and hiring funnel telemetry", now - timedelta(days=1, hours=4)),
        (AdminAuditLog.ACTION_RECRUITER_VETTING, AdminAuditLog.ENTITY_RECRUITER, 2,
         "Reviewed corporate domain authenticity and LinkedIn registration profile", now - timedelta(days=2)),
        (AdminAuditLog.ACTION_JOB_MODERATION, AdminAuditLog.ENTITY_JOB, 2,
         "Flagged and reviewed job salary disclosure requirements for compliance", now - timedelta(days=2, hours=6)),
        (AdminAuditLog.ACTION_PASSWORD_CHANGE, AdminAuditLog.ENTITY_USER, admin_user.id,
         "Admin rotated session security credentials and master password", now - timedelta(days=3)),
    ]
    for action, entity_type, entity_id, detail, ts in samples:
        entry = AdminAuditLog(
            admin_id=admin_user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail,
            created_at=ts,
        )
        db.session.add(entry)
    db.session.commit()


@admin_bp.route("/audit")
@role_required("admin")
def audit():
    _seed_audit_sample_data_if_sparse()
    page, per_page = _get_page_args(default_per_page=25)
    action_filter = request.args.get("action", "").strip()
    entity_filter = request.args.get("entity_type", "").strip()

    query = AdminAuditLog.query
    if action_filter:
        query = query.filter(AdminAuditLog.action == action_filter)
    if entity_filter:
        query = query.filter(AdminAuditLog.entity_type == entity_filter)

    logs_pagination = query.order_by(AdminAuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    all_actions = [a[0] for a in db.session.query(AdminAuditLog.action).distinct().all()]

    return render_template(
        "admin/audit.html",
        logs_pagination=logs_pagination,
        action_filter=action_filter,
        entity_filter=entity_filter,
        all_actions=all_actions,
        active_nav="audit",
    )


# ---------------------------------------------------------------------------
# 9. System Settings
# ---------------------------------------------------------------------------

@admin_bp.route("/system")
@role_required("admin")
def system():
    _seed_default_settings()
    settings = AdminSetting.query.order_by(AdminSetting.key).all()
    return render_template(
        "admin/system.html",
        settings=settings,
        active_nav="system",
    )


@admin_bp.route("/system/settings", methods=["POST"])
@role_required("admin")
def update_settings():
    for key in request.form:
        if key == "csrf_token":
            continue
        value = request.form[key].strip()
        AdminSetting.set(key, value, admin_id=current_user.id)
        _log(AdminAuditLog.ACTION_UPDATE_SETTING, AdminAuditLog.ENTITY_SETTING,
             None, f"Setting '{key}' set to '{value}'")
    db.session.commit()
    flash("Platform settings updated.", "success")
    return redirect(url_for("admin.system"))


@admin_bp.route("/system/backfill-match-scores", methods=["POST"])
@role_required("admin")
def backfill_match_scores():
    """Maintenance action: recompute match_score for every Application.

    Match scores are kept fresh at the source now (apply-time, plus
    targeted re-scores when a job's scoring inputs or a resume's content
    change) rather than recomputed on every page read. This exists to
    backfill rows that predate that change (scored_at is NULL) or to
    recover from any scorer/data drift — it is not meant to run routinely.
    """
    all_apps = Application.query.all()
    before = {a.id: a.match_score for a in all_apps}
    refresh_match_scores(all_apps)
    changed_count = sum(1 for a in all_apps if a.match_score != before[a.id])
    _log(AdminAuditLog.ACTION_BACKFILL_MATCH_SCORES, AdminAuditLog.ENTITY_APPLICATION,
         None, f"Backfilled match scores for {len(all_apps)} applications ({changed_count} changed).")
    db.session.commit()
    flash(f"Match scores recomputed for {len(all_apps)} applications ({changed_count} changed).", "success")
    return redirect(url_for("admin.system"))


# ---------------------------------------------------------------------------
# 10. Notifications (Server-Side Paginated)
# ---------------------------------------------------------------------------

@admin_bp.route("/notifications")
@role_required("admin")
def notifications():
    query = Notification.query.filter_by(candidate_id=current_user.id)
    if query.count() == 0:
        # Seed initial administrative system notifications
        now = utcnow()
        samples = [
            ("Platform Administration Activated",
             "Welcome to Zentra Administrative Console. System monitoring and audit logs are active.",
             url_for("admin.dashboard"), now - timedelta(hours=12)),
            ("Recruiter Review Queue Ready",
             "Recruiter verification system is active. Check pending submissions under Recruiters.",
             url_for("admin.recruiters", status="pending"), now - timedelta(hours=6)),
            ("Security & Rate Limiting Guard Active",
             "Exponential backoff login protection and rate limiters are currently guarding auth endpoints.",
             url_for("admin.audit"), now - timedelta(hours=1)),
        ]
        for title, msg, link, ts in samples:
            db.session.add(Notification(
                candidate_id=current_user.id,
                title=title,
                message=msg,
                link=link,
                created_at=ts,
            ))
        db.session.commit()
        query = Notification.query.filter_by(candidate_id=current_user.id)

    page, per_page = _get_page_args(default_per_page=25)
    unread_count = query.filter_by(is_read=False).count()
    notifs_pagination = query.order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template(
        "admin/notifications.html",
        notifs_pagination=notifs_pagination,
        unread_count=unread_count,
        active_nav="notifications",
    )


@admin_bp.route("/notifications/mark-read", methods=["POST"])
@role_required("admin")
def mark_notifications_read():
    Notification.query.filter_by(
        candidate_id=current_user.id, is_read=False
    ).update({"is_read": True})
    db.session.commit()
    return redirect(url_for("admin.notifications"))


# ---------------------------------------------------------------------------
# 11. Admin Profile
# ---------------------------------------------------------------------------

@admin_bp.route("/profile")
@role_required("admin")
def profile():
    return render_template(
        "admin/profile.html",
        active_nav="profile",
    )


@admin_bp.route("/profile/update", methods=["POST"])
@role_required("admin")
def update_profile():
    full_name = clean_profile_field(request.form.get("full_name"), 150)
    email_raw = clean_profile_field(request.form.get("email"), 255)
    new_password = request.form.get("new_password", "").strip()
    current_password = request.form.get("current_password", "").strip()

    if not current_user.check_password(current_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("admin.profile"))

    if full_name:
        current_user.full_name = full_name
    if email_raw and email_raw != current_user.email:
        try:
            valid = validate_email(email_raw, check_deliverability=False)
        except EmailNotValidError:
            flash("Enter a valid email address.", "error")
            return redirect(url_for("admin.profile"))
        email = valid.normalized
        existing = User.query.filter_by(email=email).first()
        if existing and existing.id != current_user.id:
            flash("That email is already in use.", "error")
            return redirect(url_for("admin.profile"))
        current_user.email = email
    if new_password:
        if len(new_password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("admin.profile"))
        if len(new_password) > 128:
            flash("Password must be at most 128 characters.", "error")
            return redirect(url_for("admin.profile"))
        current_user.set_password(new_password)

    _log(AdminAuditLog.ACTION_UPDATE_PROFILE, AdminAuditLog.ENTITY_USER,
         current_user.id, "Admin updated their own profile")
    db.session.commit()
    flash("Profile updated successfully.", "success")
    return redirect(url_for("admin.profile"))


# ---------------------------------------------------------------------------
# 9. Support Tickets (Admin Management)
# ---------------------------------------------------------------------------

@admin_bp.route("/support")
@role_required("admin")
def support_tickets():
    """Admin dashboard for viewing, searching, and filtering all support tickets."""
    page, per_page = _get_page_args(default_per_page=25)
    query = SupportTicket.query.join(User, SupportTicket.user_id == User.id)

    # Search filter (ID, user name, email, subject, description)
    q = request.args.get("q", "").strip()
    if q:
        if q.isdigit():
            query = query.filter(
                (SupportTicket.id == int(q))
                | (User.full_name.ilike(f"%{q}%"))
                | (User.email.ilike(f"%{q}%"))
                | (SupportTicket.subject.ilike(f"%{q}%"))
                | (SupportTicket.description.ilike(f"%{q}%"))
            )
        else:
            query = query.filter(
                (User.full_name.ilike(f"%{q}%"))
                | (User.email.ilike(f"%{q}%"))
                | (SupportTicket.subject.ilike(f"%{q}%"))
                | (SupportTicket.description.ilike(f"%{q}%"))
            )

    # Filter by user role (Candidate vs Recruiter)
    role_filter = request.args.get("role", "").strip()
    if role_filter in (User.ROLE_CANDIDATE, User.ROLE_RECRUITER):
        query = query.filter(User.role == role_filter)

    # Filter by ticket status
    status_filter = request.args.get("status", "").strip()
    if status_filter in SupportTicket.STATUSES:
        query = query.filter(SupportTicket.status == status_filter)

    # Filter by issue category
    issue_filter = request.args.get("issue_type", "").strip()
    if issue_filter in SupportTicket.ISSUE_TYPE_LABELS:
        query = query.filter(SupportTicket.issue_type == issue_filter)

    pagination = query.order_by(SupportTicket.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Metric summary counts
    total_open = SupportTicket.query.filter_by(status=SupportTicket.STATUS_OPEN).count()
    total_in_progress = SupportTicket.query.filter_by(status=SupportTicket.STATUS_IN_PROGRESS).count()
    total_resolved = SupportTicket.query.filter_by(status=SupportTicket.STATUS_RESOLVED).count()

    return render_template(
        "admin/support_tickets.html",
        pagination=pagination,
        tickets=pagination.items,
        total_open=total_open,
        total_in_progress=total_in_progress,
        total_resolved=total_resolved,
        q=q,
        role_filter=role_filter,
        status_filter=status_filter,
        issue_filter=issue_filter,
        active_nav="support",
    )


@admin_bp.route("/support/<int:ticket_id>", methods=["GET", "POST"])
@role_required("admin")
def support_ticket_detail(ticket_id):
    """Admin view for detailed ticket information, history, status updates, and responses."""
    import os
    from flask import current_app

    ticket = SupportTicket.query.get_or_404(ticket_id)

    if request.method == "POST":
        action = request.form.get("action", "reply").strip()

        # Handle quick status change only
        if action == "status_change":
            new_status = request.form.get("status", "").strip()
            if new_status in SupportTicket.STATUSES and new_status != ticket.status:
                old_status = ticket.status
                ticket.status = new_status
                ticket.updated_at = utcnow()

                # Notify user about the status update
                status_label = ticket.status_label
                notif = Notification(
                    candidate_id=ticket.user_id,
                    title=f"Support Ticket #{ticket.id} Status Updated",
                    message=f"Your support ticket '{ticket.subject[:40]}' status changed to '{status_label}'.",
                    link=url_for("main.support_ticket_detail", ticket_id=ticket.id),
                )
                db.session.add(notif)
                _log("support_status_change", "support_ticket", ticket.id, f"Changed status from {old_status} to {new_status}")
                db.session.commit()
                flash(f"Ticket status updated to '{status_label}'.", "success")
                return redirect(url_for("admin.support_ticket_detail", ticket_id=ticket.id))

        # Handle Admin reply with optional status change
        message_body = request.form.get("message", "").strip()
        new_status = request.form.get("status", "").strip()

        if message_body:
            attachment_filename = None
            if "attachment" in request.files:
                file = request.files["attachment"]
                if file and file.filename:
                    try:
                        inspect_file_magic(file.stream, file.filename, allowed_category="support_attachment")
                    except FileValidationError as e:
                        flash(f"Attachment rejected: {str(e)}", "error")
                        return redirect(url_for("admin.support_ticket_detail", ticket_id=ticket.id))
                    clean_name = generate_secure_stored_filename(file.filename)
                    support_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "support")
                    os.makedirs(support_dir, exist_ok=True)
                    file.save(os.path.join(support_dir, clean_name))
                    attachment_filename = clean_name

            msg = SupportTicketMessage(
                ticket_id=ticket.id,
                sender_id=current_user.id,
                message=message_body,
                attachment_filename=attachment_filename,
                is_admin_response=True,
            )
            db.session.add(msg)

            if new_status in SupportTicket.STATUSES:
                ticket.status = new_status
            ticket.updated_at = utcnow()

            # In-app notification to the ticket owner via existing notification system
            notif = Notification(
                candidate_id=ticket.user_id,
                title=f"Support Update on Ticket #{ticket.id}",
                message=f"Support team replied to your ticket '{ticket.subject[:40]}'.",
                link=url_for("main.support_ticket_detail", ticket_id=ticket.id),
            )
            db.session.add(notif)
            _log("support_reply", "support_ticket", ticket.id, f"Admin replied to ticket #{ticket.id}")
            db.session.commit()
            flash("Response sent successfully to the user.", "success")
            return redirect(url_for("admin.support_ticket_detail", ticket_id=ticket.id))
        else:
            flash("Please enter a response message.", "error")

    return render_template(
        "admin/support_ticket_detail.html",
        ticket=ticket,
        active_nav="support",
    )
