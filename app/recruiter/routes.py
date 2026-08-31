from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, abort
from flask_login import login_user, login_required, current_user
from sqlalchemy import func, or_, and_

from app import db
from app.models.user import User
from app.models.recruiter_profile import RecruiterProfile
from app.models.job import Job
from app.models.application import Application
from app.models.application_event import ApplicationEvent
from app.models.notification import Notification
from app.models.resume import Resume
from app.recruiter.forms import RecruiterRegistrationForm, JobPostForm
from app.utils.decorators import role_required, approved_recruiter_required
from app.utils.security import limiter
from app.ml.extractor import (
    extract_structured_jd,
    extract_structured_resume,
    clean_text,
)
from app.ml.ats_scorer import score_resume
from app.ai import ai_service

recruiter_bp = Blueprint("recruiter", __name__, template_folder="../templates/recruiter")


@recruiter_bp.route("/register", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config.get("RATELIMIT_AUTH", "5 per minute; 20 per hour"))
def register():
    form = RecruiterRegistrationForm()

    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.work_email.data.lower().strip()).first()
        if existing:
            flash("An account with this work email already exists.", "error")
            return render_template("recruiters.html", form=form)

        user = User(
            full_name=form.contact_name.data.strip(),
            email=form.work_email.data.lower().strip(),
            role=User.ROLE_RECRUITER,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        profile = RecruiterProfile(
            user_id=user.id,
            company_name=form.company_name.data.strip(),
            industry=form.industry.data,
            company_size=form.company_size.data,
            company_website=form.company_website.data,
            contact_role=form.contact_role.data,
            phone=form.phone.data,
            hiring_needs=form.hiring_needs.data,
            approval_status=RecruiterProfile.STATUS_PENDING,
        )
        db.session.add(profile)
        db.session.commit()

        login_user(user)
        flash(
            "Thanks — your company is submitted for review. "
            "You'll be able to post jobs once an admin approves your account.",
            "success",
        )
        return redirect(url_for("recruiter.dashboard"))

    return render_template("recruiters.html", form=form)


# ----------------------------------------------------------------------
# 1. DASHBOARD
# ----------------------------------------------------------------------
@recruiter_bp.route("/dashboard")
@role_required("recruiter")
def dashboard():
    profile = current_user.recruiter_profile
    jobs = []
    active_jobs_count = 0
    total_applicants_count = 0
    shortlisted_count = 0
    interviews_count = 0
    recent_activity = []
    hiring_alerts = []

    if profile and profile.approval_status == RecruiterProfile.STATUS_APPROVED:
        jobs = Job.query.filter_by(recruiter_profile_id=profile.id).order_by(Job.created_at.desc()).all()
        active_jobs_count = sum(1 for j in jobs if j.status == Job.STATUS_ACTIVE)
        
        job_ids = [j.id for j in jobs]
        if job_ids:
            all_apps = Application.query.filter(Application.job_id.in_(job_ids)).all()
            total_applicants_count = len(all_apps)
            shortlisted_count = sum(1 for a in all_apps if a.status == Application.STATUS_SHORTLISTED)
            interviews_count = sum(1 for a in all_apps if a.status == Application.STATUS_INTERVIEW)
            
            # Recent application events / applications
            recent_activity = (
                Application.query.filter(Application.job_id.in_(job_ids))
                .order_by(Application.applied_at.desc())
                .limit(6)
                .all()
            )
            
            unreviewed = [a for a in all_apps if a.status == Application.STATUS_APPLIED]
            if unreviewed:
                hiring_alerts.append({
                    "type": "info",
                    "title": f"{len(unreviewed)} new application{'s' if len(unreviewed) != 1 else ''} awaiting review",
                    "desc": "Check your incoming candidate applications and AI match scores.",
                    "link": url_for("recruiter.candidates"),
                })
            
            top_matches = [a for a in all_apps if a.status == Application.STATUS_APPLIED and (a.match_score or 0) >= 80]
            if top_matches:
                hiring_alerts.append({
                    "type": "success",
                    "title": f"{len(top_matches)} top-tier match candidate{'s' if len(top_matches) != 1 else ''} (80%+ score)",
                    "desc": "High AI relevance candidate matches are waiting in your pipeline.",
                    "link": url_for("recruiter.pipeline"),
                })

    return render_template(
        "recruiter/dashboard.html",
        profile=profile,
        jobs=jobs,
        active_jobs_count=active_jobs_count,
        total_applicants_count=total_applicants_count,
        shortlisted_count=shortlisted_count,
        interviews_count=interviews_count,
        recent_activity=recent_activity,
        hiring_alerts=hiring_alerts,
        active_nav="dashboard",
    )


# ----------------------------------------------------------------------
# 2. JOBS (Workspace & AI Analysis)
# ----------------------------------------------------------------------
@recruiter_bp.route("/jobs")
@role_required("recruiter")
def jobs():
    profile = current_user.recruiter_profile
    if not profile or profile.approval_status != RecruiterProfile.STATUS_APPROVED:
        return redirect(url_for("recruiter.dashboard"))

    status_filter = request.args.get("status", "all").lower().strip()
    q = request.args.get("q", "").strip()

    query = Job.query.filter_by(recruiter_profile_id=profile.id)
    if status_filter in [Job.STATUS_ACTIVE, Job.STATUS_DRAFT, Job.STATUS_PAUSED, Job.STATUS_CLOSED]:
        query = query.filter_by(status=status_filter)

    if q:
        query = query.filter(
            or_(
                Job.title.ilike(f"%{q}%"),
                Job.location.ilike(f"%{q}%"),
                Job.description.ilike(f"%{q}%"),
            )
        )

    all_jobs = query.order_by(Job.created_at.desc()).all()
    
    counts = {
        "all": Job.query.filter_by(recruiter_profile_id=profile.id).count(),
        "active": Job.query.filter_by(recruiter_profile_id=profile.id, status=Job.STATUS_ACTIVE).count(),
        "draft": Job.query.filter_by(recruiter_profile_id=profile.id, status=Job.STATUS_DRAFT).count(),
        "paused": Job.query.filter_by(recruiter_profile_id=profile.id, status=Job.STATUS_PAUSED).count(),
        "closed": Job.query.filter_by(recruiter_profile_id=profile.id, status=Job.STATUS_CLOSED).count(),
    }

    # Attach stats for each job
    job_cards = []
    for j in all_jobs:
        apps = j.applications
        job_cards.append({
            "job": j,
            "total_applicants": len(apps),
            "shortlisted": sum(1 for a in apps if a.status == Application.STATUS_SHORTLISTED),
            "interviews": sum(1 for a in apps if a.status == Application.STATUS_INTERVIEW),
            "hired": sum(1 for a in apps if a.status == Application.STATUS_HIRED),
            "avg_match": round(sum(a.match_score for a in apps if a.match_score) / len(apps), 1) if apps else None,
        })

    return render_template(
        "recruiter/jobs.html",
        job_cards=job_cards,
        status_filter=status_filter,
        q=q,
        counts=counts,
        active_nav="jobs",
    )


@recruiter_bp.route("/jobs/new", methods=["GET", "POST"])
@approved_recruiter_required
def new_job():
    form = JobPostForm()
    if form.validate_on_submit():
        job_status = form.status.data if hasattr(form, "status") and form.status.data in Job.STATUSES else Job.STATUS_ACTIVE
        job = Job(
            recruiter_profile_id=current_user.recruiter_profile.id,
            title=form.title.data.strip(),
            description=form.description.data,
            responsibilities=form.responsibilities.data,
            requirements=form.requirements.data,
            job_type=form.job_type.data,
            work_mode=form.work_mode.data,
            experience_level=form.experience_level.data,
            location=form.location.data,
            salary_min=_safe_int(form.salary_min.data),
            salary_max=_safe_int(form.salary_max.data),
            status=job_status,
        )
        db.session.add(job)
        db.session.commit()
        flash(f"Job saved as '{job_status.capitalize()}'. Zentra AI has analyzed the requirements.", "success")
        return redirect(url_for("recruiter.job_overview", job_id=job.id))
    return render_template("recruiter/job_form.html", form=form, active_nav="jobs")


@recruiter_bp.route("/jobs/<int:job_id>/status", methods=["POST"])
@approved_recruiter_required
def update_job_status(job_id):
    job = Job.query.filter_by(
        id=job_id, recruiter_profile_id=current_user.recruiter_profile.id
    ).first_or_404()
    
    new_status = request.form.get("status", "").strip().lower()
    return_to = request.form.get("return_to", "jobs")
    
    if new_status in Job.STATUSES:
        job.status = new_status
        db.session.commit()
        flash(f"Job status updated to '{new_status.capitalize()}'.", "success")
    else:
        flash("Invalid job status specified.", "error")
        
    if return_to == "overview":
        return redirect(url_for("recruiter.job_overview", job_id=job.id))
    return redirect(url_for("recruiter.jobs"))


@recruiter_bp.route("/jobs/<int:job_id>/overview")
@approved_recruiter_required
def job_overview(job_id):
    job = Job.query.filter_by(
        id=job_id, recruiter_profile_id=current_user.recruiter_profile.id
    ).first_or_404()
    
    apps = job.applications
    total_applicants = len(apps)
    
    progress = {
        "applied": sum(1 for a in apps if a.status == Application.STATUS_APPLIED),
        "under_review": sum(1 for a in apps if a.status == Application.STATUS_UNDER_REVIEW),
        "shortlisted": sum(1 for a in apps if a.status == Application.STATUS_SHORTLISTED),
        "interview": sum(1 for a in apps if a.status == Application.STATUS_INTERVIEW),
        "hired": sum(1 for a in apps if a.status == Application.STATUS_HIRED),
        "rejected": sum(1 for a in apps if a.status == Application.STATUS_REJECTED),
    }
    
    # Run structured JD analysis with ATS extractor engine
    full_jd_text = f"{job.title}\n{job.description}\n{job.responsibilities or ''}\n{job.requirements or ''}"
    structured_jd = extract_structured_jd(full_jd_text)

    top_candidates = sorted(apps, key=lambda a: a.match_score or 0, reverse=True)[:5]

    return render_template(
        "recruiter/job_overview.html",
        job=job,
        structured_jd=structured_jd,
        total_applicants=total_applicants,
        progress=progress,
        shortlisted=progress["shortlisted"],
        interviews=progress["interview"],
        hired=progress["hired"],
        top_candidates=top_candidates,
        active_nav="jobs",
        active_tab="overview",
    )


@recruiter_bp.route("/jobs/<int:job_id>/applicants")
@approved_recruiter_required
def applicants(job_id):
    job = Job.query.filter_by(
        id=job_id, recruiter_profile_id=current_user.recruiter_profile.id
    ).first_or_404()
    
    apps = (
        Application.query.filter_by(job_id=job.id)
        .order_by(Application.match_score.desc())
        .all()
    )

    full_jd_text = f"{job.title}\n{job.description}\n{job.responsibilities or ''}\n{job.requirements or ''}"
    structured_jd = extract_structured_jd(full_jd_text)
    jd_req_skills = structured_jd.get("required_skills", []) or structured_jd.get("technical_skills", [])
    jd_min_years = structured_jd.get("experience", {}).get("min_years")
    jd_degrees = structured_jd.get("education", {}).get("degrees", [])

    # Enrich each application with deep matching evidence
    app_evidence = []
    for app in apps:
        resume_text = app.resume.raw_text if app.resume else ""
        structured_resume = extract_structured_resume(resume_text)
        res_skills = set(structured_resume.get("skills", []))
        
        matched_skills = [s for s in jd_req_skills if s in res_skills]
        missing_skills = [s for s in jd_req_skills if s not in res_skills]
        
        res_years = structured_resume.get("experience", {}).get("min_years")
        if res_years is not None and jd_min_years is not None:
            exp_match_text = f"{res_years:g} yrs / {jd_min_years:g}+ yrs req"
            exp_matched = res_years >= jd_min_years
        elif res_years is not None:
            exp_match_text = f"{res_years:g} yrs experience"
            exp_matched = True
        else:
            exp_match_text = f"{job.experience_level.capitalize()} level"
            exp_matched = True

        res_degs = structured_resume.get("education", {}).get("degrees", [])
        if res_degs:
            edu_text = f"{res_degs[0]} degree"
            edu_matched = True
        else:
            edu_text = "Education listed" if structured_resume.get("education", {}).get("has_education") else "No degree listed"
            edu_matched = bool(structured_resume.get("education", {}).get("has_education"))

        app_evidence.append({
            "application": app,
            "matched_skills": matched_skills[:5],
            "missing_skills": missing_skills[:4],
            "exp_match_text": exp_match_text,
            "exp_matched": exp_matched,
            "edu_text": edu_text,
            "edu_matched": edu_matched,
            "score": app.match_score or 0,
        })

    return render_template(
        "recruiter/applicants.html",
        job=job,
        applications=apps,
        app_evidence=app_evidence,
        active_nav="jobs",
        active_tab="applicants",
    )


@recruiter_bp.route("/jobs/<int:job_id>/applicants/bulk-status", methods=["POST"])
@approved_recruiter_required
def bulk_update_applicant_status(job_id):
    job = Job.query.filter_by(
        id=job_id, recruiter_profile_id=current_user.recruiter_profile.id
    ).first_or_404()

    new_status = request.form.get("status", "").strip()
    raw_ids = request.form.getlist("application_ids")
    ids_str = request.form.get("application_ids_str", "")

    app_ids = []
    for val in raw_ids:
        if str(val).isdigit():
            app_ids.append(int(val))
    if ids_str:
        for part in ids_str.split(","):
            if part.strip().isdigit():
                app_ids.append(int(part.strip()))

    app_ids = list(set(app_ids))

    if not app_ids:
        flash("No candidates were selected for bulk action.", "error")
        return redirect(url_for("recruiter.applicants", job_id=job.id))

    if new_status not in Application.STATUSES:
        flash("Invalid target status specified.", "error")
        return redirect(url_for("recruiter.applicants", job_id=job.id))

    apps_to_update = Application.query.filter(
        Application.id.in_(app_ids),
        Application.job_id == job.id,
    ).all()

    status_label = new_status.replace("_", " ").title()
    for app in apps_to_update:
        app.status = new_status
        db.session.add(ApplicationEvent(
            application_id=app.id,
            status=new_status,
            note=f"Bulk updated to '{status_label}' by recruiter.",
        ))
        db.session.add(Notification(
            candidate_id=app.candidate_id,
            title=f"Application update: {job.title}",
            message=f"Your application status has been updated to '{status_label}'.",
            link=f"/candidate/applications/{app.id}",
        ))

    db.session.commit()
    flash(f"Successfully updated {len(apps_to_update)} candidate{'s' if len(apps_to_update) != 1 else ''} to '{status_label}'.", "success")
    return redirect(url_for("recruiter.applicants", job_id=job.id))


@recruiter_bp.route("/jobs/<int:job_id>/shortlist")
@approved_recruiter_required
def job_shortlist(job_id):
    job = Job.query.filter_by(
        id=job_id, recruiter_profile_id=current_user.recruiter_profile.id
    ).first_or_404()
    
    shortlisted_apps = (
        Application.query.filter(
            Application.job_id == job.id,
            or_(Application.status == Application.STATUS_SHORTLISTED, Application.match_score >= 70)
        )
        .order_by(Application.match_score.desc())
        .all()
    )
    return render_template("recruiter/job_shortlist.html", job=job, applications=shortlisted_apps, active_nav="jobs", active_tab="shortlist")


@recruiter_bp.route("/jobs/<int:job_id>/compare")
@approved_recruiter_required
def compare_candidates(job_id):
    job = Job.query.filter_by(
        id=job_id, recruiter_profile_id=current_user.recruiter_profile.id
    ).first_or_404()
    
    # Get selected application IDs from query params (e.g. ?apps=1,2,3)
    apps_param = request.args.get("apps", "")
    app_ids = [int(i.strip()) for i in apps_param.split(",") if i.strip().isdigit()]
    
    if not app_ids:
        # Default to top 3 applications by match score
        top_apps = Application.query.filter_by(job_id=job.id).order_by(Application.match_score.desc()).limit(3).all()
        app_ids = [a.id for a in top_apps]

    selected_apps = (
        Application.query.filter(Application.id.in_(app_ids), Application.job_id == job.id)
        .all()
    ) if app_ids else []

    full_jd_text = f"{job.title}\n{job.description}\n{job.responsibilities or ''}\n{job.requirements or ''}"
    structured_jd = extract_structured_jd(full_jd_text)
    all_jd_skills = structured_jd.get("required_skills", []) + structured_jd.get("bonus_skills", [])
    if not all_jd_skills:
        all_jd_skills = structured_jd.get("technical_skills", [])[:10]

    # Build comparison columns
    candidate_cols = []
    for app in selected_apps:
        resume_text = app.resume.raw_text if app.resume else ""
        structured_resume = extract_structured_resume(resume_text)
        res_skills = set(structured_resume.get("skills", []))
        
        # Build skills map: skill -> bool (has skill)
        skills_map = {skill: (skill in res_skills) for skill in all_jd_skills}
        matched_count = sum(1 for has in skills_map.values() if has)
        
        res_years = structured_resume.get("experience", {}).get("min_years")
        res_seniority = structured_resume.get("experience", {}).get("seniority", "mid")
        res_degs = structured_resume.get("education", {}).get("degrees", [])

        candidate_cols.append({
            "application": app,
            "candidate": app.candidate,
            "score": app.match_score or 0,
            "skills_map": skills_map,
            "matched_count": matched_count,
            "missing_skills": [s for s in all_jd_skills if s not in res_skills],
            "experience_years": f"{res_years:g} yrs" if res_years else "Not stated",
            "seniority": res_seniority.capitalize(),
            "degrees": ", ".join(res_degs) if res_degs else "General degree",
        })

    all_job_apps = Application.query.filter_by(job_id=job.id).order_by(Application.match_score.desc()).all()

    return render_template(
        "recruiter/compare.html",
        job=job,
        all_jd_skills=all_jd_skills,
        candidate_cols=candidate_cols,
        all_job_apps=all_job_apps,
        selected_app_ids=app_ids,
        active_nav="jobs",
    )


@recruiter_bp.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@approved_recruiter_required
def edit_job(job_id):
    job = Job.query.filter_by(
        id=job_id, recruiter_profile_id=current_user.recruiter_profile.id
    ).first_or_404()
    form = JobPostForm(obj=job)
    if form.validate_on_submit():
        job.title = form.title.data.strip()
        job.description = form.description.data
        job.responsibilities = form.responsibilities.data
        job.requirements = form.requirements.data
        job.job_type = form.job_type.data
        job.work_mode = form.work_mode.data
        job.experience_level = form.experience_level.data
        job.location = form.location.data
        job.salary_min = _safe_int(form.salary_min.data)
        job.salary_max = _safe_int(form.salary_max.data)
        db.session.commit()
        flash("Job updated.", "success")
        return redirect(url_for("recruiter.jobs"))
    return render_template("recruiter/job_form.html", form=form, editing=True, job=job, active_nav="jobs")


@recruiter_bp.route("/jobs/<int:job_id>/close", methods=["POST"])
@approved_recruiter_required
def close_job(job_id):
    job = Job.query.filter_by(
        id=job_id, recruiter_profile_id=current_user.recruiter_profile.id
    ).first_or_404()
    job.status = Job.STATUS_CLOSED
    db.session.commit()
    flash("Job closed — it will no longer appear in job search.", "info")
    return redirect(url_for("recruiter.jobs"))


@recruiter_bp.route("/jobs/<int:job_id>/reopen", methods=["POST"])
@approved_recruiter_required
def reopen_job(job_id):
    job = Job.query.filter_by(
        id=job_id, recruiter_profile_id=current_user.recruiter_profile.id
    ).first_or_404()
    job.status = Job.STATUS_ACTIVE
    db.session.commit()
    flash("Job reopened — it is live again on the jobs board.", "success")
    return redirect(url_for("recruiter.jobs"))


# ----------------------------------------------------------------------
# 3. CANDIDATES & CANDIDATE INTELLIGENCE
# ----------------------------------------------------------------------
@recruiter_bp.route("/candidates")
@role_required("recruiter")
def candidates():
    profile = current_user.recruiter_profile
    if not profile or profile.approval_status != RecruiterProfile.STATUS_APPROVED:
        return redirect(url_for("recruiter.dashboard"))

    q = request.args.get("q", "").strip()
    skill_filter = request.args.get("skill", "").strip()
    exp_filter = request.args.get("experience", "").strip()
    min_score = request.args.get("score", "").strip()

    recruiter_jobs = Job.query.filter_by(recruiter_profile_id=profile.id).all()
    job_ids = [j.id for j in recruiter_jobs]

    candidates_query = User.query.filter_by(role=User.ROLE_CANDIDATE, is_active_account=True)

    # Candidate Privacy Enforcement: candidate must be discoverable OR have an active application to recruiter's jobs
    if job_ids:
        applied_cand_ids_subquery = db.session.query(Application.candidate_id).filter(Application.job_id.in_(job_ids)).subquery()
        candidates_query = candidates_query.filter(
            or_(
                User.recruiter_discoverable.is_(True),
                User.id.in_(applied_cand_ids_subquery)
            )
        )
    else:
        candidates_query = candidates_query.filter(User.recruiter_discoverable.is_(True))

    if q:
        candidates_query = candidates_query.filter(
            or_(
                User.full_name.ilike(f"%{q}%"),
                User.headline.ilike(f"%{q}%"),
                User.skills.ilike(f"%{q}%"),
                User.location.ilike(f"%{q}%"),
            )
        )
    if skill_filter:
        candidates_query = candidates_query.filter(User.skills.ilike(f"%{skill_filter}%"))
    if exp_filter:
        candidates_query = candidates_query.filter_by(experience_level=exp_filter)

    candidates_list = candidates_query.limit(40).all()

    candidate_records = []
    for cand in candidates_list:
        cand_apps = [a for a in cand.applications if a.job_id in job_ids] if job_ids else []
        best_score = max([a.match_score for a in cand_apps if a.match_score is not None], default=None)
        skills = [s.strip() for s in (cand.skills or "").split(",") if s.strip()]
        
        candidate_records.append({
            "user": cand,
            "skills": skills[:6],
            "all_skills": skills,
            "applications": cand_apps,
            "best_match_score": best_score,
            "latest_resume": cand.resumes[-1] if cand.resumes else None,
            "primary_app": cand_apps[0] if cand_apps else None,
        })

    if min_score:
        try:
            score_val = float(min_score)
            candidate_records = [c for c in candidate_records if c["best_match_score"] and c["best_match_score"] >= score_val]
        except ValueError:
            pass

    return render_template(
        "recruiter/candidates.html",
        candidates=candidate_records,
        q=q,
        skill_filter=skill_filter,
        exp_filter=exp_filter,
        min_score=min_score,
        active_nav="candidates",
    )


@recruiter_bp.route("/candidates/<int:candidate_id>/intelligence")
@role_required("recruiter")
def candidate_intelligence(candidate_id):
    profile = current_user.recruiter_profile
    if not profile or profile.approval_status != RecruiterProfile.STATUS_APPROVED:
        return redirect(url_for("recruiter.dashboard"))

    candidate = User.query.filter_by(id=candidate_id, role=User.ROLE_CANDIDATE, is_active_account=True).first_or_404()
    
    # Recruiter's jobs
    recruiter_jobs = Job.query.filter_by(recruiter_profile_id=profile.id).order_by(Job.created_at.desc()).all()
    job_ids = [j.id for j in recruiter_jobs]

    # Applications submitted by this candidate to this recruiter's jobs
    applications = Application.query.filter(
        Application.candidate_id == candidate.id,
        Application.job_id.in_(job_ids)
    ).all() if job_ids else []

    # Privacy Enforcement: deny access if candidate is not discoverable and has no applications to recruiter's jobs
    if not candidate.recruiter_discoverable and not applications:
        abort(404)

    # Selected job context
    selected_job_id = request.args.get("job_id", type=int)
    target_job = None
    target_app = None

    if selected_job_id:
        target_job = Job.query.filter_by(id=selected_job_id, recruiter_profile_id=profile.id).first()
    
    if not target_job and applications:
        target_app = applications[0]
        target_job = target_app.job
    elif not target_job and recruiter_jobs:
        target_job = recruiter_jobs[0]

    if target_job and applications:
        target_app = next((a for a in applications if a.job_id == target_job.id), applications[0])

    # Latest Resume
    resume = candidate.resumes[-1] if candidate.resumes else None
    resume_text = resume.raw_text if resume else (candidate.experience or "")

    # Run deep ATS scoring and structured intelligence
    match_data = None
    structured_jd = None
    structured_resume = extract_structured_resume(resume_text)

    if target_job:
        full_jd = f"{target_job.title}\n{target_job.description}\n{target_job.responsibilities or ''}\n{target_job.requirements or ''}"
        structured_jd = extract_structured_jd(full_jd)
        if resume_text:
            match_data = score_resume(resume_text, full_jd)

    # AI Dossier & Interview Questions Generation
    ai_briefing = None
    ai_interview_questions = None
    ai_provider_used = "local"
    if target_job and match_data:
        cand_skills = [s.strip() for s in (candidate.skills or "").split(",") if s.strip()]
        ai_briefing, p1 = ai_service.generate_candidate_summary(
            candidate_name=candidate.full_name,
            headline=candidate.headline or "",
            skills=cand_skills,
            experience_summary=candidate.experience or "",
            job_title=target_job.title,
            match_score=match_data.get("score", 0),
        )
        ai_interview_questions, p2 = ai_service.generate_interview_questions(
            job_title=target_job.title,
            requirements=target_job.requirements or target_job.description or "",
            candidate_skills=cand_skills,
            missing_skills=match_data.get("missing_keywords", []),
        )
        ai_provider_used = p1

    # Recruiter timeline events & notes
    timeline_events = []
    if target_app:
        timeline_events = target_app.events

    return render_template(
        "recruiter/candidate_intelligence.html",
        candidate=candidate,
        resume=resume,
        structured_resume=structured_resume,
        target_job=target_job,
        target_app=target_app,
        applications=applications,
        recruiter_jobs=recruiter_jobs,
        match_data=match_data,
        structured_jd=structured_jd,
        timeline_events=timeline_events,
        ai_briefing=ai_briefing,
        ai_interview_questions=ai_interview_questions,
        ai_provider_used=ai_provider_used,
        active_nav="candidates",
    )


@recruiter_bp.route("/api/improve-jd", methods=["POST"])
@approved_recruiter_required
def api_improve_jd():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title") or "").strip()
    raw_desc = str(data.get("description") or "").strip()
    reqs = str(data.get("requirements") or "").strip()

    if not title:
        return jsonify({"status": "error", "message": "Job title is required"}), 400

    improved_jd, provider_used = ai_service.improve_job_description(title, raw_desc, requirements=reqs)
    return jsonify({
        "status": "success",
        "improved": improved_jd,
        "provider_used": provider_used,
    })


@recruiter_bp.route("/applications/<int:application_id>/intelligence")
@role_required("recruiter")
def application_intelligence(application_id):
    app = (
        Application.query.join(Job)
        .filter(
            Application.id == application_id,
            Job.recruiter_profile_id == current_user.recruiter_profile.id
        )
        .first_or_404()
    )
    return redirect(url_for("recruiter.candidate_intelligence", candidate_id=app.candidate_id, job_id=app.job_id))


@recruiter_bp.route("/applications/<int:application_id>/add-note", methods=["POST"])
@approved_recruiter_required
def add_recruiter_note(application_id):
    app = (
        Application.query.join(Job)
        .filter(
            Application.id == application_id,
            Job.recruiter_profile_id == current_user.recruiter_profile.id
        )
        .first_or_404()
    )
    note_text = request.form.get("note", "").strip()
    if note_text:
        event = ApplicationEvent(
            application_id=app.id,
            status=app.status,
            note=f"Recruiter Note: {note_text}"
        )
        db.session.add(event)
        db.session.commit()
        flash("Private recruiter note added to candidate timeline.", "success")
    
    return redirect(url_for("recruiter.candidate_intelligence", candidate_id=app.candidate_id, job_id=app.job_id))


# ----------------------------------------------------------------------
# 4. HIRING PIPELINE (Interactive Kanban)
# ----------------------------------------------------------------------
@recruiter_bp.route("/pipeline")
@role_required("recruiter")
def pipeline():
    profile = current_user.recruiter_profile
    if not profile or profile.approval_status != RecruiterProfile.STATUS_APPROVED:
        return redirect(url_for("recruiter.dashboard"))

    selected_job_id = request.args.get("job_id", type=int)
    recruiter_jobs = Job.query.filter_by(recruiter_profile_id=profile.id).order_by(Job.created_at.desc()).all()
    job_ids = [j.id for j in recruiter_jobs]

    app_query = Application.query
    if selected_job_id:
        app_query = app_query.filter_by(job_id=selected_job_id)
    elif job_ids:
        app_query = app_query.filter(Application.job_id.in_(job_ids))
    else:
        app_query = app_query.filter(Application.id == -1)

    all_apps = app_query.order_by(Application.applied_at.desc()).all()

    columns = {
        "applied": [a for a in all_apps if a.status == Application.STATUS_APPLIED],
        "under_review": [a for a in all_apps if a.status == Application.STATUS_UNDER_REVIEW],
        "shortlisted": [a for a in all_apps if a.status == Application.STATUS_SHORTLISTED],
        "interview": [a for a in all_apps if a.status == Application.STATUS_INTERVIEW],
        "hired": [a for a in all_apps if a.status == Application.STATUS_HIRED],
        "rejected": [a for a in all_apps if a.status == Application.STATUS_REJECTED],
    }

    return render_template(
        "recruiter/pipeline.html",
        jobs=recruiter_jobs,
        selected_job_id=selected_job_id,
        columns=columns,
        total_count=len(all_apps),
        active_nav="pipeline",
    )


# ----------------------------------------------------------------------
# 5. ANALYTICS
# ----------------------------------------------------------------------
@recruiter_bp.route("/analytics")
@role_required("recruiter")
def analytics():
    profile = current_user.recruiter_profile
    if not profile or profile.approval_status != RecruiterProfile.STATUS_APPROVED:
        return redirect(url_for("recruiter.dashboard"))

    jobs = Job.query.filter_by(recruiter_profile_id=profile.id).all()
    job_ids = [j.id for j in jobs]
    
    total_apps = 0
    shortlisted = 0
    interviews = 0
    hired = 0
    rejected = 0
    scores = []
    job_stats = []
    
    if job_ids:
        all_apps = Application.query.filter(Application.job_id.in_(job_ids)).all()
        total_apps = len(all_apps)
        shortlisted = sum(1 for a in all_apps if a.status == Application.STATUS_SHORTLISTED)
        interviews = sum(1 for a in all_apps if a.status == Application.STATUS_INTERVIEW)
        hired = sum(1 for a in all_apps if a.status == Application.STATUS_HIRED)
        rejected = sum(1 for a in all_apps if a.status == Application.STATUS_REJECTED)
        scores = [a.match_score for a in all_apps if a.match_score is not None]

        for j in jobs:
            j_apps = [a for a in all_apps if a.job_id == j.id]
            avg_score = (sum(a.match_score for a in j_apps if a.match_score) / len(j_apps)) if j_apps else 0
            job_stats.append({
                "job": j,
                "applicants_count": len(j_apps),
                "shortlisted_count": sum(1 for a in j_apps if a.status == Application.STATUS_SHORTLISTED),
                "hired_count": sum(1 for a in j_apps if a.status == Application.STATUS_HIRED),
                "avg_score": round(avg_score, 1),
            })

    shortlist_rate = round((shortlisted / total_apps * 100), 1) if total_apps > 0 else 0
    interview_rate = round((interviews / total_apps * 100), 1) if total_apps > 0 else 0
    hire_rate = round((hired / total_apps * 100), 1) if total_apps > 0 else 0
    avg_match = round(sum(scores) / len(scores), 1) if scores else 0
    
    c_90 = sum(1 for s in scores if s >= 90)
    c_75 = sum(1 for s in scores if 75 <= s < 90)
    c_60 = sum(1 for s in scores if 60 <= s < 75)
    c_low = sum(1 for s in scores if s < 60)

    match_distribution = {
        "count_90": c_90,
        "count_75": c_75,
        "count_60": c_60,
        "count_low": c_low,
        "pct_90": round((c_90 / total_apps * 100), 1) if total_apps > 0 else 0,
        "pct_75": round((c_75 / total_apps * 100), 1) if total_apps > 0 else 0,
        "pct_60": round((c_60 / total_apps * 100), 1) if total_apps > 0 else 0,
        "pct_low": round((c_low / total_apps * 100), 1) if total_apps > 0 else 0,
    }

    return render_template(
        "recruiter/analytics.html",
        total_apps=total_apps,
        shortlist_rate=shortlist_rate,
        interview_rate=interview_rate,
        hire_rate=hire_rate,
        avg_match=avg_match,
        hired=hired,
        match_distribution=match_distribution,
        job_stats=job_stats,
        active_nav="analytics",
    )


# ----------------------------------------------------------------------
# 6. NOTIFICATIONS
# ----------------------------------------------------------------------
@recruiter_bp.route("/notifications")
@role_required("recruiter")
def notifications():
    user_notifications = (
        Notification.query.filter_by(candidate_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return render_template("recruiter/notifications.html", notifications=user_notifications, active_nav="notifications")


@recruiter_bp.route("/notifications/read-all", methods=["POST"])
@role_required("recruiter")
def mark_notifications_read():
    Notification.query.filter_by(candidate_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("recruiter.notifications"))


# ----------------------------------------------------------------------
# 7. PROFILE & SETTINGS
# ----------------------------------------------------------------------
@recruiter_bp.route("/profile", methods=["GET", "POST"])
@role_required("recruiter")
def profile():
    recruiter_profile = current_user.recruiter_profile
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        contact_role = request.form.get("contact_role", "").strip()
        phone = request.form.get("phone", "").strip()
        
        if full_name:
            current_user.full_name = full_name
        if recruiter_profile:
            recruiter_profile.contact_role = contact_role
            recruiter_profile.phone = phone
        db.session.commit()
        flash("Your profile was updated successfully.", "success")
        return redirect(url_for("recruiter.profile"))

    return render_template("recruiter/profile.html", profile=recruiter_profile, active_nav="profile")


@recruiter_bp.route("/company", methods=["GET", "POST"])
@role_required("recruiter")
def company_profile():
    recruiter_profile = current_user.recruiter_profile
    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        industry = request.form.get("industry", "").strip()
        company_size = request.form.get("company_size", "").strip()
        company_website = request.form.get("company_website", "").strip()
        hiring_needs = request.form.get("hiring_needs", "").strip()

        if recruiter_profile:
            if company_name:
                recruiter_profile.company_name = company_name
            recruiter_profile.industry = industry
            recruiter_profile.company_size = company_size
            recruiter_profile.company_website = company_website
            recruiter_profile.hiring_needs = hiring_needs
            db.session.commit()
            flash("Company profile updated successfully.", "success")
        return redirect(url_for("recruiter.company_profile"))

    return render_template("recruiter/company_profile.html", profile=recruiter_profile, active_nav="company_profile")


@recruiter_bp.route("/settings", methods=["GET", "POST"])
@role_required("recruiter")
def settings():
    if request.method == "POST":
        new_password = request.form.get("new_password", "").strip()
        if new_password:
            if len(new_password) < 8:
                flash("Password must be at least 8 characters long.", "error")
            elif len(new_password) > 128:
                flash("Password exceeds the maximum allowed length.", "error")
            else:
                current_user.set_password(new_password)
                db.session.commit()
                flash("Password updated successfully.", "success")
        return redirect(url_for("recruiter.settings"))

    return render_template("recruiter/settings.html", active_nav="settings")


# ----------------------------------------------------------------------
# APPLICATION STATUS CONTROLLER
# ----------------------------------------------------------------------
@recruiter_bp.route("/applications/<int:application_id>/status", methods=["POST"])
@approved_recruiter_required
def update_application_status(application_id):
    application = (
        Application.query
        .join(Job, Application.job_id == Job.id)
        .filter(
            Application.id == application_id,
            Job.recruiter_profile_id == current_user.recruiter_profile.id,
        )
        .first_or_404()
    )
    new_status = request.form.get("status", "").strip()
    return_to = request.form.get("return_to", "applicants")
    
    valid_transitions = {
        Application.STATUS_APPLIED: [Application.STATUS_UNDER_REVIEW, Application.STATUS_SHORTLISTED, Application.STATUS_REJECTED],
        Application.STATUS_UNDER_REVIEW: [Application.STATUS_SHORTLISTED, Application.STATUS_INTERVIEW, Application.STATUS_REJECTED],
        Application.STATUS_SHORTLISTED: [Application.STATUS_INTERVIEW, Application.STATUS_HIRED, Application.STATUS_REJECTED],
        Application.STATUS_INTERVIEW: [Application.STATUS_HIRED, Application.STATUS_SHORTLISTED, Application.STATUS_REJECTED],
        Application.STATUS_REJECTED: [Application.STATUS_UNDER_REVIEW, Application.STATUS_SHORTLISTED],
        Application.STATUS_HIRED: [Application.STATUS_REJECTED],
    }

    if new_status not in Application.STATUSES:
        flash("Invalid status specified.", "error")
        return redirect(url_for("recruiter.applicants", job_id=application.job_id))

    if new_status != application.status and new_status not in valid_transitions.get(application.status, []):
        flash(f"Cannot transition application directly from '{application.status.title()}' to '{new_status.title()}'.", "error")
        return redirect(url_for("recruiter.applicants", job_id=application.job_id))

    note = request.form.get("note", "").strip() or None
    application.status = new_status
    db.session.add(ApplicationEvent(
        application_id=application.id,
        status=new_status,
        note=note or f"Status updated to {new_status.replace('_', ' ')} by recruiter.",
    ))

    status_label = new_status.replace("_", " ").title()
    db.session.add(Notification(
        candidate_id=application.candidate_id,
        title=f"Application update: {application.job.title}",
        message=f"Your application status has been updated to '{status_label}'.",
        link=f"/candidate/applications/{application.id}",
    ))
    db.session.commit()
    flash(f"Candidate status updated to '{status_label}'.", "success")

    if return_to == "pipeline":
        return redirect(url_for("recruiter.pipeline", job_id=application.job_id))
    elif return_to == "intelligence":
        return redirect(url_for("recruiter.candidate_intelligence", candidate_id=application.candidate_id, job_id=application.job_id))
    return redirect(url_for("recruiter.applicants", job_id=application.job_id))


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
