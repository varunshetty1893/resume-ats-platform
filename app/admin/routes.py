"""Zentra Admin Blueprint — complete platform administration routes with server-side pagination."""

from collections import defaultdict
from datetime import datetime, timedelta

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
from app.utils.decorators import role_required

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


@admin_bp.context_processor
def admin_context():
    """Inject platform-wide counters needed by the admin sidebar on every page."""
    from app.models.recruiter_profile import RecruiterProfile as RP
    pending = RP.query.filter_by(approval_status=RP.STATUS_PENDING).count()
    return {"pending_recruiter_count": pending}


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
    total_applications = Application.query.count()
    total_shortlisted = Application.query.filter_by(status=Application.STATUS_SHORTLISTED).count()
    total_interviews = Application.query.filter_by(status=Application.STATUS_INTERVIEW).count()
    total_hires = Application.query.filter_by(status=Application.STATUS_HIRED).count()
    pending_recruiters = RecruiterProfile.query.filter_by(
        approval_status=RecruiterProfile.STATUS_PENDING
    ).count()

    # Distinct company count
    total_companies = db.session.query(
        func.count(func.distinct(RecruiterProfile.company_name))
    ).scalar() or 0

    # Recent platform activity (last 10 audit entries)
    recent_audit = AdminAuditLog.query.order_by(
        AdminAuditLog.created_at.desc()
    ).limit(10).all()

    # Recent applications (last 10)
    recent_applications = Application.query.order_by(
        Application.applied_at.desc()
    ).limit(10).all()

    # Last 7 days application trend
    seven_days = []
    for i in range(6, -1, -1):
        day = datetime.utcnow().date() - timedelta(days=i)
        count = Application.query.filter(
            func.date(Application.applied_at) == day
        ).count()
        seven_days.append({"day": day.strftime("%b %d"), "count": count})

    stats = dict(
        total_users=total_users,
        total_candidates=total_candidates,
        total_recruiters=total_recruiters,
        total_companies=total_companies,
        total_jobs=total_jobs,
        total_applications=total_applications,
        total_shortlisted=total_shortlisted,
        total_interviews=total_interviews,
        total_hires=total_hires,
        pending_recruiters=pending_recruiters,
    )
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_audit=recent_audit,
        recent_applications=recent_applications,
        seven_days=seven_days,
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
    profile = RecruiterProfile.query.get_or_404(profile_id)
    audit_entries = AdminAuditLog.query.filter_by(
        entity_type=AdminAuditLog.ENTITY_RECRUITER, entity_id=profile_id
    ).order_by(AdminAuditLog.created_at.desc()).limit(20).all()
    return render_template(
        "admin/recruiter_detail.html",
        profile=profile,
        audit_entries=audit_entries,
        active_nav="recruiters",
    )


@admin_bp.route("/recruiters/<int:profile_id>/approve", methods=["POST"])
@role_required("admin")
def approve_recruiter(profile_id):
    profile = RecruiterProfile.query.get_or_404(profile_id)
    profile.approval_status = RecruiterProfile.STATUS_APPROVED
    profile.reviewed_at = datetime.utcnow()
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
    reason = request.form.get("reason", "").strip() or None
    profile.approval_status = RecruiterProfile.STATUS_REJECTED
    profile.reviewed_at = datetime.utcnow()
    profile.reviewed_by_admin_id = current_user.id
    profile.rejection_reason = reason
    _log(AdminAuditLog.ACTION_REJECT_RECRUITER, AdminAuditLog.ENTITY_RECRUITER, profile_id,
         f"Rejected recruiter: {profile.company_name}. Reason: {reason or 'none'}")
    db.session.add(Notification(
        user_id=profile.user_id,
        title="Company application not approved",
        message=reason or "Your company application was not approved at this time.",
        link=url_for("recruiter.dashboard"),
    ))
    db.session.commit()
    flash(f"{profile.company_name} rejected.", "info")
    return redirect(url_for("admin.recruiters"))


# ---------------------------------------------------------------------------
# 4. Companies (Server-Side Paginated)
# ---------------------------------------------------------------------------

@admin_bp.route("/companies")
@role_required("admin")
def companies():
    page, per_page = _get_page_args(default_per_page=25)
    q = request.args.get("q", "").strip()

    # Query distinct company names and their stats using GROUP BY
    query = (
        db.session.query(
            RecruiterProfile.company_name.label("name"),
            func.count(func.distinct(RecruiterProfile.id)).label("recruiter_count"),
        )
        .filter(RecruiterProfile.approval_status == RecruiterProfile.STATUS_APPROVED)
    )
    if q:
        query = query.filter(RecruiterProfile.company_name.ilike(f"%{q}%"))

    grouped_query = query.group_by(RecruiterProfile.company_name).order_by(RecruiterProfile.company_name.asc())
    companies_pagination = grouped_query.paginate(page=page, per_page=per_page, error_out=False)

    # For the items on the current page, compute aggregate metrics efficiently
    companies_list = []
    for item in companies_pagination.items:
        c_name = item.name
        profiles = RecruiterProfile.query.filter_by(company_name=c_name, approval_status=RecruiterProfile.STATUS_APPROVED).all()
        job_count = sum(len(p.jobs) for p in profiles)
        app_count = sum(sum(len(j.applications) for j in p.jobs) for p in profiles)
        hire_count = sum(sum(sum(1 for a in j.applications if a.status == Application.STATUS_HIRED) for j in p.jobs) for p in profiles)
        companies_list.append({
            "name": c_name,
            "profiles": profiles,
            "recruiter_count": item.recruiter_count,
            "job_count": job_count,
            "app_count": app_count,
            "hire_count": hire_count,
        })

    return render_template(
        "admin/companies.html",
        companies_list=companies_list,
        companies_pagination=companies_pagination,
        q=q,
        active_nav="companies",
    )


@admin_bp.route("/companies/<path:company_name>")
@role_required("admin")
def company_detail(company_name):
    profiles = RecruiterProfile.query.filter_by(company_name=company_name).all()
    if not profiles:
        abort(404)
    all_jobs = [j for p in profiles for j in p.jobs]
    all_apps = [a for j in all_jobs for a in j.applications]
    return render_template(
        "admin/company_detail.html",
        company_name=company_name,
        profiles=profiles,
        all_jobs=all_jobs,
        all_apps=all_apps,
        Application=Application,
        active_nav="companies",
    )


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
# 6. Applications (Server-Side Paginated)
# ---------------------------------------------------------------------------

@admin_bp.route("/applications")
@role_required("admin")
def applications():
    page, per_page = _get_page_args(default_per_page=25)
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = (
        Application.query
        .join(User, Application.candidate_id == User.id)
        .join(Job, Application.job_id == Job.id)
        .join(RecruiterProfile, Job.recruiter_profile_id == RecruiterProfile.id)
    )
    if q:
        like = f"%{q}%"
        query = query.filter(
            User.full_name.ilike(like) | User.email.ilike(like) | Job.title.ilike(like) | RecruiterProfile.company_name.ilike(like)
        )
    if status_filter in Application.STATUSES:
        query = query.filter(Application.status == status_filter)

    apps_pagination = query.order_by(Application.applied_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    status_counts = {s: Application.query.filter_by(status=s).count() for s in Application.STATUSES}
    status_counts["all"] = Application.query.count()

    return render_template(
        "admin/applications.html",
        apps_pagination=apps_pagination,
        q=q,
        status_filter=status_filter,
        status_counts=status_counts,
        active_nav="applications",
    )


@admin_bp.route("/applications/<int:app_id>")
@role_required("admin")
def application_detail(app_id):
    app_obj = Application.query.get_or_404(app_id)
    return render_template(
        "admin/application_detail.html",
        app=app_obj,
        active_nav="applications",
    )


# ---------------------------------------------------------------------------
# 7. Reports (Bounded & Database Aggregated)
# ---------------------------------------------------------------------------

@admin_bp.route("/reports")
@role_required("admin")
def reports():
    # Monthly user registrations (last 6 months)
    monthly_users = []
    for i in range(5, -1, -1):
        month_start = (datetime.utcnow().replace(day=1) - timedelta(days=i * 30)).replace(day=1)
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

    # Top recruiting companies (Strictly limited to top 10)
    top_companies = (
        db.session.query(
            RecruiterProfile.company_name,
            func.count(Job.id).label("job_count")
        )
        .join(Job, Job.recruiter_profile_id == RecruiterProfile.id)
        .group_by(RecruiterProfile.company_name)
        .order_by(func.count(Job.id).desc())
        .limit(10)
        .all()
    )

    return render_template(
        "admin/reports.html",
        monthly_users=monthly_users,
        funnel=funnel,
        job_status_dist=job_status_dist,
        approval_stats=approval_stats,
        score_buckets=score_buckets,
        top_companies=top_companies,
        active_nav="reports",
    )


# ---------------------------------------------------------------------------
# 8. Audit Log (Server-Side Paginated)
# ---------------------------------------------------------------------------

@admin_bp.route("/audit")
@role_required("admin")
def audit():
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


# ---------------------------------------------------------------------------
# 10. Notifications (Server-Side Paginated)
# ---------------------------------------------------------------------------

@admin_bp.route("/notifications")
@role_required("admin")
def notifications():
    page, per_page = _get_page_args(default_per_page=25)
    query = Notification.query.filter_by(candidate_id=current_user.id)
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
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    new_password = request.form.get("new_password", "").strip()
    current_password = request.form.get("current_password", "").strip()

    if not current_user.check_password(current_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("admin.profile"))

    if full_name:
        current_user.full_name = full_name
    if email and email != current_user.email:
        existing = User.query.filter_by(email=email).first()
        if existing and existing.id != current_user.id:
            flash("That email is already in use.", "error")
            return redirect(url_for("admin.profile"))
        current_user.email = email
    if new_password:
        if len(new_password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("admin.profile"))
        current_user.set_password(new_password)

    _log(AdminAuditLog.ACTION_UPDATE_PROFILE, AdminAuditLog.ENTITY_USER,
         current_user.id, "Admin updated their own profile")
    db.session.commit()
    flash("Profile updated successfully.", "success")
    return redirect(url_for("admin.profile"))
