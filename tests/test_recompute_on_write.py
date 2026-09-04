"""Integration tests for the recompute-on-write match_score logic (Phase 1).

Before this change, match_score was recomputed on every read (Dashboard,
Pipeline, Analytics, Candidates, ...) instead of being kept fresh at the
source. This suite exercises the real write paths end-to-end through the
Flask test client and asserts:

1. Applying to a job scores the application exactly once, at apply time.
2. Editing a job's scoring-relevant fields (required_skills_raw here)
   re-scores every application *for that job* — and only that job.
3. Editing an unrelated job does not touch another job's applications.
4. Editing a candidate's resume in place (resume builder save) re-scores
   every application pinned to that resume.
"""

import unittest
from datetime import timedelta
from app.utils.time import utcnow

from app import create_app, db
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.application import Application
from app.models.recruiter_profile import RecruiterProfile
from app.ml.ats_scorer import score_resume_for_job


class TestRecomputeOnWrite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()

        cls.recruiter_user = User(
            full_name="Rescore Recruiter",
            email="rescore_recruiter@example.com",
            role=User.ROLE_RECRUITER,
            is_active_account=True,
        )
        cls.recruiter_user.set_password("Recruiter@1234")
        db.session.add(cls.recruiter_user)
        db.session.flush()

        cls.rec_profile = RecruiterProfile(
            user_id=cls.recruiter_user.id,
            company_name="RescoreCorp",
            approval_status=RecruiterProfile.STATUS_APPROVED,
        )
        db.session.add(cls.rec_profile)
        db.session.flush()

        deadline = utcnow() + timedelta(days=30)

        cls.job_a = Job(
            recruiter_profile_id=cls.rec_profile.id,
            title="Backend Engineer",
            description="Build REST APIs with Flask and PostgreSQL.",
            required_skills_raw="Python, Flask, PostgreSQL",
            status=Job.STATUS_ACTIVE,
            application_deadline=deadline,
        )
        cls.job_b = Job(
            recruiter_profile_id=cls.rec_profile.id,
            title="Frontend Engineer",
            description="Build UI with React and TypeScript.",
            required_skills_raw="React, TypeScript",
            status=Job.STATUS_ACTIVE,
            application_deadline=deadline,
        )
        db.session.add_all([cls.job_a, cls.job_b])
        db.session.flush()

        cls.candidate = User(
            full_name="Rescore Candidate",
            email="rescore_candidate@example.com",
            role=User.ROLE_CANDIDATE,
            is_active_account=True,
            public_slug="rescore-candidate",
        )
        cls.candidate.set_password("Candidate@1234")
        db.session.add(cls.candidate)
        db.session.commit()

        cls.job_a_id = cls.job_a.id
        cls.job_b_id = cls.job_b.id
        cls.candidate_id = cls.candidate.id

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        cls.app_context.pop()

    def setUp(self):
        db.session.rollback()
        with self.app.test_request_context():
            from flask_login import logout_user
            logout_user()

    def tearDown(self):
        db.session.rollback()
        with self.app.test_request_context():
            from flask_login import logout_user
            logout_user()

    def _login(self, email, password):
        with self.app.test_request_context():
            from flask_login import logout_user
            logout_user()
        client = self.app.test_client()
        client.post(
            "/auth/login",
            data={"login-email": email, "login-password": password, "login-submit": "Log in"},
        )
        return client

    def _edit_job_form_data(self, job, **overrides):
        deadline = (utcnow() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M")
        data = {
            "title": job.title,
            "description": job.description,
            "responsibilities": job.responsibilities or "",
            "requirements": job.requirements or "",
            "required_skills_raw": job.required_skills_raw,
            "preferred_skills_raw": job.preferred_skills_raw or "",
            "job_type": "full_time",
            "work_mode": "remote",
            "experience_level": "mid",
            "location": "Remote",
            "salary_min": "",
            "salary_max": "",
            "application_deadline": deadline,
            "status": job.status,
        }
        data.update(overrides)
        return data

    def test_01_apply_scores_once_at_create_time(self):
        resume = Resume(candidate_id=self.candidate_id, source="paste", raw_text="Experienced with Python, Flask, and PostgreSQL.")
        db.session.add(resume)
        db.session.commit()

        client = self._login("rescore_candidate@example.com", "Candidate@1234")
        resp = client.post(f"/candidate/jobs/{self.job_a_id}/apply", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        application = Application.query.filter_by(job_id=self.job_a_id, candidate_id=self.candidate_id).first()
        self.assertIsNotNone(application)
        self.assertIsNotNone(application.scored_at)

        job_a = db.session.get(Job, self.job_a_id)
        expected_score = score_resume_for_job(resume.raw_text, job_a)["score"]
        self.assertEqual(application.match_score, expected_score)

    def test_02_editing_jobs_scoring_inputs_rescores_only_that_jobs_applications(self):
        # Fresh candidate + resume + application pinned to job_a, and a
        # second application on the unrelated job_b, so we can assert one
        # gets re-scored and the other doesn't.
        candidate = User(
            full_name="Rescore Candidate Two",
            email="rescore_candidate_2@example.com",
            role=User.ROLE_CANDIDATE,
            is_active_account=True,
            public_slug="rescore-candidate-2",
        )
        candidate.set_password("Candidate@1234")
        db.session.add(candidate)
        db.session.flush()

        resume = Resume(candidate_id=candidate.id, source="paste", raw_text="Skilled in Python and Flask, some PostgreSQL.")
        db.session.add(resume)
        db.session.flush()

        job_a = db.session.get(Job, self.job_a_id)
        job_b = db.session.get(Job, self.job_b_id)

        original_score_a = score_resume_for_job(resume.raw_text, job_a)["score"]
        application_a = Application(
            job_id=self.job_a_id, candidate_id=candidate.id, resume_id=resume.id,
            match_score=original_score_a, scored_at=utcnow(),
        )
        original_score_b = score_resume_for_job(resume.raw_text, job_b)["score"]
        application_b = Application(
            job_id=self.job_b_id, candidate_id=candidate.id, resume_id=resume.id,
            match_score=original_score_b, scored_at=utcnow(),
        )
        db.session.add_all([application_a, application_b])
        db.session.commit()
        app_a_id, app_b_id = application_a.id, application_b.id
        stamp_a_before = application_a.scored_at
        stamp_b_before = application_b.scored_at

        # Add a skill to job_a that this resume doesn't have — the score
        # for job_a's application should change; job_b's must not move.
        client = self._login("rescore_recruiter@example.com", "Recruiter@1234")
        form_data = self._edit_job_form_data(job_a, required_skills_raw="Python, Flask, PostgreSQL, Kubernetes, Docker")
        resp = client.post(f"/recruiter/jobs/{self.job_a_id}/edit", data=form_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        db.session.expire_all()
        refreshed_a = db.session.get(Application, app_a_id)
        refreshed_b = db.session.get(Application, app_b_id)

        expected_new_score_a = score_resume_for_job(resume.raw_text, db.session.get(Job, self.job_a_id))["score"]
        self.assertEqual(refreshed_a.match_score, expected_new_score_a)
        self.assertNotEqual(refreshed_a.match_score, original_score_a)
        self.assertGreater(refreshed_a.scored_at, stamp_a_before)

        # job_b's application is completely untouched by editing job_a.
        self.assertEqual(refreshed_b.match_score, original_score_b)
        self.assertEqual(refreshed_b.scored_at, stamp_b_before)

    def test_03_editing_an_unrelated_job_does_not_touch_other_jobs_applications(self):
        candidate = User(
            full_name="Rescore Candidate Three",
            email="rescore_candidate_3@example.com",
            role=User.ROLE_CANDIDATE,
            is_active_account=True,
            public_slug="rescore-candidate-3",
        )
        candidate.set_password("Candidate@1234")
        db.session.add(candidate)
        db.session.flush()

        resume = Resume(candidate_id=candidate.id, source="paste", raw_text="Python and Flask developer.")
        db.session.add(resume)
        db.session.flush()

        job_a = db.session.get(Job, self.job_a_id)
        score = score_resume_for_job(resume.raw_text, job_a)["score"]
        application = Application(
            job_id=self.job_a_id, candidate_id=candidate.id, resume_id=resume.id,
            match_score=score, scored_at=utcnow(),
        )
        db.session.add(application)
        db.session.commit()
        app_id = application.id
        stamp_before = application.scored_at
        score_before = application.match_score

        # Edit job_b (which this candidate never applied to) — job_a's
        # application must be completely unaffected.
        client = self._login("rescore_recruiter@example.com", "Recruiter@1234")
        job_b = db.session.get(Job, self.job_b_id)
        form_data = self._edit_job_form_data(job_b, required_skills_raw="React, TypeScript, GraphQL")
        resp = client.post(f"/recruiter/jobs/{self.job_b_id}/edit", data=form_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        db.session.expire_all()
        refreshed = db.session.get(Application, app_id)
        self.assertEqual(refreshed.match_score, score_before)
        self.assertEqual(refreshed.scored_at, stamp_before)

    def test_04_editing_resume_in_place_rescores_pinned_applications(self):
        candidate = User(
            full_name="Rescore Candidate Four",
            email="rescore_candidate_4@example.com",
            role=User.ROLE_CANDIDATE,
            is_active_account=True,
            public_slug="rescore-candidate-4",
        )
        candidate.set_password("Candidate@1234")
        db.session.add(candidate)
        db.session.flush()

        resume = Resume(candidate_id=candidate.id, source="builder", name="My Resume", raw_text="Python developer.")
        db.session.add(resume)
        db.session.flush()

        job_a = db.session.get(Job, self.job_a_id)
        original_score = score_resume_for_job(resume.raw_text, job_a)["score"]
        application = Application(
            job_id=self.job_a_id, candidate_id=candidate.id, resume_id=resume.id,
            match_score=original_score, scored_at=utcnow(),
        )
        db.session.add(application)
        db.session.commit()
        app_id = application.id
        resume_id = resume.id
        stamp_before = application.scored_at

        client = self._login("rescore_candidate_4@example.com", "Candidate@1234")
        resp = client.post(
            "/candidate/api/resume-builder/save",
            json={
                "resume_id": resume_id,
                "resume_name": "My Resume",
                "target_role": "Backend Engineer",
                "resume_data": {
                    "summary": "Python, Flask, and PostgreSQL developer with backend experience.",
                    "skills": ["Python", "Flask", "PostgreSQL"],
                    "experience": [],
                    "education": [],
                    "projects": [],
                },
            },
        )
        self.assertEqual(resp.status_code, 200)

        db.session.expire_all()
        refreshed_resume = db.session.get(Resume, resume_id)
        refreshed_application = db.session.get(Application, app_id)

        expected_new_score = score_resume_for_job(refreshed_resume.raw_text, db.session.get(Job, self.job_a_id))["score"]
        self.assertEqual(refreshed_application.match_score, expected_new_score)
        self.assertNotEqual(refreshed_application.match_score, original_score)
        self.assertGreater(refreshed_application.scored_at, stamp_before)


if __name__ == "__main__":
    unittest.main()
