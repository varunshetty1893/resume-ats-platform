from datetime import datetime

from flask import Blueprint, render_template, request, current_app, abort
from flask_login import current_user
from sqlalchemy import or_

from app.models.job import Job
from app.models.resume import Resume
from app.models.saved_job import SavedJob
from app.models.user import User
from app.models.career_entry import CareerEntry
from app.ml.job_matcher import rank_jobs_for_resume, match_breakdown
from app.utils.security import limiter

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@limiter.limit(lambda: current_app.config.get("RATELIMIT_PUBLIC", "30 per minute"))
def landing():
    return render_template("landing.html")


@main_bp.route("/about")
@limiter.limit(lambda: current_app.config.get("RATELIMIT_PUBLIC", "30 per minute"))
def about():
    return render_template("about.html")


@main_bp.route("/terms")
def terms():
    return render_template("terms.html", now=datetime.utcnow())


@main_bp.route("/privacy")
def privacy():
    return render_template("privacy.html", now=datetime.utcnow())


@main_bp.route("/profile/<slug>")
def public_profile(slug):
    candidate = User.query.filter_by(public_slug=slug, public_profile_enabled=True, role=User.ROLE_CANDIDATE, is_active_account=True).first_or_404()
    entries = {
        entry_type: [entry for entry in candidate.career_entries if entry.entry_type == entry_type]
        for entry_type in CareerEntry.TYPES
    }
    public_resume = None
    if candidate.public_resume_enabled:
        public_resume = Resume.query.filter_by(candidate_id=candidate.id).order_by(Resume.created_at.desc()).first()
    return render_template("public_profile.html", candidate=candidate, entries=entries, public_resume=public_resume)


@main_bp.route("/jobs")
def jobs():
    query = Job.query.filter_by(status=Job.STATUS_ACTIVE)

    keyword = request.args.get("q", "").strip()
    if keyword:
        query = query.filter(or_(
            Job.title.ilike(f"%{keyword}%"), Job.description.ilike(f"%{keyword}%"),
            Job.requirements.ilike(f"%{keyword}%"), Job.location.ilike(f"%{keyword}%"),
        ))

    levels = request.args.getlist("experience")
    if levels:
        query = query.filter(Job.experience_level.in_(levels))
    modes = request.args.getlist("work_mode")
    if modes:
        query = query.filter(Job.work_mode.in_(modes))
    job_types = request.args.getlist("job_type")
    if job_types:
        query = query.filter(Job.job_type.in_(job_types))
    salary_min = request.args.get("salary_min", type=int)
    salary_max = request.args.get("salary_max", type=int)
    if salary_min is not None:
        query = query.filter(Job.salary_max >= salary_min)
    if salary_max is not None:
        query = query.filter(Job.salary_min <= salary_max)

    all_jobs = query.order_by(Job.created_at.desc()).all()

    resume_text = _latest_resume_text()
    ranked = rank_jobs_for_resume(resume_text, all_jobs)

    saved_job_ids = set()
    if current_user.is_authenticated and current_user.is_candidate:
        saved_job_ids = {item.job_id for item in SavedJob.query.filter_by(candidate_id=current_user.id).all()}
    match_explanations = {}
    if resume_text:
        for job, _score in ranked:
            match_explanations[job.id] = match_breakdown(resume_text, job)
    return render_template("jobs.html", ranked_jobs=ranked, saved_job_ids=saved_job_ids, match_explanations=match_explanations)


@main_bp.route("/jobs/<int:job_id>")
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)

    if job.status == Job.STATUS_DRAFT:
        is_owner = (
            current_user.is_authenticated
            and current_user.is_recruiter
            and current_user.recruiter_profile
            and current_user.recruiter_profile.id == job.recruiter_profile_id
        )
        if not (current_user.is_authenticated and (current_user.is_admin or is_owner)):
            abort(404)

    resume_text = _latest_resume_text()
    breakdown = match_breakdown(resume_text, job) if resume_text else None

    is_saved = current_user.is_authenticated and current_user.is_candidate and SavedJob.query.filter_by(candidate_id=current_user.id, job_id=job.id).first() is not None
    return render_template("job_detail.html", job=job, breakdown=breakdown, is_saved=is_saved)


def _latest_resume_text():
    if not (current_user.is_authenticated and current_user.is_candidate):
        return None
    resume = (
        Resume.query.filter_by(candidate_id=current_user.id)
        .order_by(Resume.created_at.desc())
        .first()
    )
    return resume.raw_text if resume else None
