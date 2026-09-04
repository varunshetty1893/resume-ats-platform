# Zentra — Resume ATS Checker + Job Seeking Platform

Flask + PostgreSQL backend for the Zentra frontend (landing, auth, about,
recruiters, resume-ai, jobs, job-detail pages).

## Stack
- Python 3.11+, Flask 3
- PostgreSQL (via SQLAlchemy) — falls back to local SQLite if `DATABASE_URL`
  isn't set, so you can run this without Postgres while developing.
- Flask-Login for sessions, Flask-WTF for forms + CSRF
- scikit-learn (TF-IDF + cosine similarity) for ATS scoring
- pypdf / python-docx for resume text extraction
- Tailwind CDN + Bootstrap Icons in the templates (matches the frontend
  mockups already built)

## Roles
- **candidate** — signs up directly, checks ATS score, builds a resume, applies to jobs
- **recruiter** — registers via `/recruiter/register` with company details;
  account stays `pending` until an admin approves it, then can post jobs
- **admin** — approves/rejects recruiter registrations at `/admin`

Recruiters and candidates log in from the **same** `/auth/login` page — there's
no separate "recruiter login".

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# edit .env — set SECRET_KEY and DATABASE_URL (Postgres) or leave
# DATABASE_URL unset to use local SQLite for dev

python seed.py                  # creates tables + a default admin account
python run.py                   # http://127.0.0.1:5000
```

### If you see "column X does not exist"

This happens when the models change (new fields added) after you already
created your database tables. Instead of dropping everything, run:

```bash
python sync_schema.py
```

It adds any missing columns/tables without touching existing data. Safe to
re-run any time.

Default admin login (change the password after first login):
```
admin@zentra.example.com / Admin@123
```

## Folder structure

```
app/
  models/        User, RecruiterProfile, Resume, Job, Application
  auth/          login, candidate signup, logout
  candidate/     dashboard, ATS checker, resume builder, apply-to-job
  recruiter/     company registration, dashboard, post job, view applicants
  admin/         recruiter approval queue
  main/          public pages: landing, about, jobs list, job detail
  ml/            resume_parser.py, ats_scorer.py, job_matcher.py
  templates/     Jinja templates (base.html + one per page/blueprint)
  static/        css/js/img + resume uploads
run.py           dev server entry point
seed.py          creates tables + default admin
```

## Notes / next steps
- `seed.py` uses `db.create_all()` for a quick start. For real migrations,
  switch to Flask-Migrate: `flask db init && flask db migrate && flask db upgrade`.
- ATS scoring is TF-IDF + cosine similarity — good for an MVP demo, not a
  production-grade NLP model. Swap `app/ml/ats_scorer.py` if you want to
  plug in a stronger model later.
- File uploads are saved to `app/static/uploads` — move this to S3/Cloud
  Storage before deploying anywhere with an ephemeral filesystem.
- No email sending is wired up yet (e.g. "you're approved" notifications) —
  admin approvals just flip a DB flag for now.
