"""One-off setup script:
  1. Creates all tables (equivalent to a first migration).
  2. Creates a default admin account so someone can log in and approve
     recruiters.
  3. Seeds a handful of sample companies + job postings (the same ones
     referenced on the landing page — TechCorp Solutions, DataSphere, etc.)
     so the Jobs page has real content out of the box.

Run with:  python seed.py
Safe to re-run — everything here is guarded by "does this already exist".
"""

import os
from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models.user import User
from app.models.recruiter_profile import RecruiterProfile
from app.models.job import Job

app = create_app()

# Admin credentials — override via ADMIN_SEED_EMAIL / ADMIN_SEED_PASSWORD env vars
# The defaults below are ONLY for development / demo. Always change in production.
ADMIN_EMAIL = os.environ.get("ADMIN_SEED_EMAIL", "admin@zentra.example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_SEED_PASSWORD", "Admin@123")

# Matches the companies already referenced on the landing page / mockups —
# TechCorp Solutions and DataSphere appear in the "Opportunities, curated
# for you" section; Nexova and Flowbyte were in the jobs page mockup.
SAMPLE_COMPANIES = [
    {
        "contact_name": "Priya Nair",
        "contact_role": "Talent Acquisition Lead",
        "email": "hiring@techcorp.example.com",
        "company_name": "TechCorp Solutions",
        "industry": "technology",
        "company_size": "201-500",
        "company_website": "https://techcorp.example.com",
        "jobs": [{
            "title": "Senior AI Engineer",
            "description": (
                "We're looking for a Senior AI Engineer to design and ship machine "
                "learning systems that power candidate-job matching at scale. You'll "
                "own models end-to-end — from data pipeline to production inference "
                "— and work closely with product on what a 'good match' means."
            ),
            "responsibilities": (
                "Design and train ranking/matching models on resume and job "
                "description data.\nOwn the ML pipeline from feature engineering to "
                "deployment.\nPartner with backend engineers to serve predictions at "
                "low latency.\nSet up evaluation frameworks to track model quality."
            ),
            "requirements": (
                "4+ years building and shipping ML systems in production.\n"
                "Strong Python, with hands-on experience in PyTorch or TensorFlow.\n"
                "Comfortable with NLP — embeddings, similarity search, transformers.\n"
                "Experience with React is a plus, not required."
            ),
            "job_type": "full_time", "work_mode": "remote", "experience_level": "senior",
            "location": "Remote", "salary_min": 28, "salary_max": 36,
        }],
    },
    {
        "contact_name": "Marcus Webb",
        "contact_role": "Head of Talent",
        "email": "hiring@datasphere.example.com",
        "company_name": "DataSphere",
        "industry": "technology",
        "company_size": "500+",
        "company_website": "https://datasphere.example.com",
        "jobs": [{
            "title": "Machine Learning Lead",
            "description": (
                "DataSphere is hiring a Machine Learning Lead to guide our MLOps "
                "practice and mentor a growing team of ML engineers. You'll set "
                "technical direction for model deployment, monitoring, and "
                "retraining pipelines across the platform."
            ),
            "responsibilities": (
                "Lead a team of 4 ML engineers, setting technical direction and "
                "reviewing designs.\nOwn the MLOps stack — deployment, monitoring, "
                "retraining pipelines.\nCollaborate with data science on model "
                "architecture decisions.\nDrive best practices for reproducibility "
                "and experiment tracking."
            ),
            "requirements": (
                "6+ years in ML engineering, 2+ in a lead or mentoring role.\n"
                "Deep experience with TensorFlow and MLOps tooling.\n"
                "Track record of taking models from research to production.\n"
                "Strong team management and cross-functional communication skills."
            ),
            "job_type": "full_time", "work_mode": "onsite", "experience_level": "lead",
            "location": "New York, NY", "salary_min": 35, "salary_max": 45,
        }],
    },
    {
        "contact_name": "Ananya Rao",
        "contact_role": "HR Manager",
        "email": "careers@nexova.example.com",
        "company_name": "Nexova",
        "industry": "technology",
        "company_size": "51-200",
        "company_website": "https://nexova.example.com",
        "jobs": [{
            "title": "Backend Engineer — Flask",
            "description": (
                "Nexova is looking for a Backend Engineer to build and maintain "
                "REST APIs powering our core product. You'll work with Flask and "
                "PostgreSQL in a small, fast-moving team where your code ships the "
                "same week you write it."
            ),
            "responsibilities": (
                "Build and maintain REST APIs using Flask.\nDesign PostgreSQL "
                "schemas and write efficient queries.\nWrite tests and participate "
                "in code review.\nCollaborate directly with frontend and product on "
                "feature scoping."
            ),
            "requirements": (
                "2+ years of Python backend experience.\nHands-on with Flask (or a "
                "similar framework) and PostgreSQL.\nComfortable designing and "
                "consuming REST APIs.\nBonus: experience with SQLAlchemy and "
                "Docker."
            ),
            "job_type": "full_time", "work_mode": "hybrid", "experience_level": "mid",
            "location": "Bengaluru, Hybrid", "salary_min": 14, "salary_max": 20,
        }],
    },
    {
        "contact_name": "Jordan Lee",
        "contact_role": "People Ops",
        "email": "jobs@flowbyte.example.com",
        "company_name": "Flowbyte",
        "industry": "technology",
        "company_size": "11-50",
        "company_website": "https://flowbyte.example.com",
        "jobs": [{
            "title": "Frontend Developer",
            "description": (
                "Flowbyte is a small remote-first team building developer tools. "
                "We're hiring a Frontend Developer to own the UI layer of our main "
                "product — clean component design, fast iteration, and a strong "
                "eye for detail."
            ),
            "responsibilities": (
                "Build and maintain UI components in JavaScript/React.\nTranslate "
                "designs into responsive, accessible interfaces.\nWork with "
                "Tailwind CSS for styling and design consistency.\nCollaborate "
                "async with a fully remote team."
            ),
            "requirements": (
                "2+ years of frontend development experience.\nStrong JavaScript "
                "fundamentals; React experience preferred.\nComfortable with "
                "Tailwind CSS or a similar utility-first framework.\nComfortable "
                "working async in a remote team."
            ),
            "job_type": "full_time", "work_mode": "remote", "experience_level": "mid",
            "location": "Remote", "salary_min": 10, "salary_max": 16,
        }],
    },
]

# Sample recruiter default password — override via RECRUITER_SEED_PASSWORD env var
DEFAULT_RECRUITER_PASSWORD = os.environ.get("RECRUITER_SEED_PASSWORD", "SampleRecruiter123!")

with app.app_context():
    db.create_all()

    if not User.query.filter_by(email=ADMIN_EMAIL).first():
        admin = User(
            full_name="Zentra Admin",
            email=ADMIN_EMAIL,
            role=User.ROLE_ADMIN,
        )
        admin.set_password(ADMIN_PASSWORD)
        db.session.add(admin)
        db.session.commit()
        print(f"Created admin user: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print("Change this password after first login.")
    else:
        print("Admin user already exists — skipped.")

    for company in SAMPLE_COMPANIES:
        user = User.query.filter_by(email=company["email"]).first()
        if user is None:
            user = User(
                full_name=company["contact_name"],
                email=company["email"],
                role=User.ROLE_RECRUITER,
            )
            user.set_password(DEFAULT_RECRUITER_PASSWORD)
            db.session.add(user)
            db.session.flush()

            profile = RecruiterProfile(
                user_id=user.id,
                company_name=company["company_name"],
                industry=company["industry"],
                company_size=company["company_size"],
                company_website=company["company_website"],
                contact_role=company["contact_role"],
                approval_status=RecruiterProfile.STATUS_APPROVED,
            )
            db.session.add(profile)
            db.session.flush()
            print(f"Created recruiter: {company['company_name']} ({company['email']})")
        else:
            profile = user.recruiter_profile

        for job_data in company["jobs"]:
            existing_job = Job.query.filter_by(
                recruiter_profile_id=profile.id, title=job_data["title"]
            ).first()
            if existing_job:
                continue
            job = Job(recruiter_profile_id=profile.id, **job_data)
            db.session.add(job)
            print(f"  + posted job: {job_data['title']}")

    db.session.commit()
    print(f"\nSample recruiter login password (all companies): {DEFAULT_RECRUITER_PASSWORD}")
    print("Database tables ready.")
