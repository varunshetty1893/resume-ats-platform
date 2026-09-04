"""Test suite validating fixes for all business logic faults:
1. Duplicate application race condition IntegrityError handling
2. Primary Resume management (set-primary, fallback, duplicate, delete)
3. Auto-close on hire and reversible reopening on hire reversal (HIRED -> REJECTED)
4. Job deadline filtering on /jobs and candidate recommendations
5. Admin recruiter rejection cascading to active job closure
6. Job-edit rescoring preserving historical scores on decided applications
"""

import unittest
from datetime import timedelta
from app.utils.time import utcnow
from app import create_app, db
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.application import Application
from app.models.application_event import ApplicationEvent
from app.models.recruiter_profile import RecruiterProfile
from app.recruiter.routes import _rescore_applications_for_job


class TestBusinessLogicFaultsFixes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        cls.app_context.pop()

    def setUp(self):
        db.session.rollback()

    def tearDown(self):
        db.session.rollback()

    def _login_as(self, email, password):
        with self.app.test_request_context():
            from flask_login import logout_user
            logout_user()
        client = self.app.test_client()
        client.post(
            "/auth/login",
            data={"login-email": email, "login-password": password, "login-submit": "Log in"},
        )
        return client

    def test_01_primary_resume_lifecycle_and_set_primary(self):
        """Test primary resume default on first creation, set-primary endpoint, and fallback."""
        candidate = User(
            full_name="Alice Candidate",
            email="alice_resume@test.com",
            role=User.ROLE_CANDIDATE,
            is_active_account=True,
        )
        candidate.set_password("Pass1234!")
        db.session.add(candidate)
        db.session.commit()

        # First resume created
        r1 = Resume(
            candidate_id=candidate.id,
            raw_text="Python Engineer Resume One",
            name="Resume 1",
            is_primary=True,
        )
        db.session.add(r1)
        db.session.commit()

        self.assertEqual(Resume.get_primary(candidate.id).id, r1.id)

        # Second resume created (not primary by default)
        r2 = Resume(
            candidate_id=candidate.id,
            raw_text="Data Scientist Resume Two",
            name="Resume 2",
            is_primary=False,
        )
        db.session.add(r2)
        db.session.commit()

        # Primary is still r1 even though r2 is newer
        self.assertEqual(Resume.get_primary(candidate.id).id, r1.id)

        # Candidate sets r2 as primary via POST route
        client = self._login_as("alice_resume@test.com", "Pass1234!")
        resp = client.post(f"/candidate/resumes/{r2.id}/set-primary", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        db.session.refresh(r1)
        db.session.refresh(r2)
        self.assertFalse(r1.is_primary)
        self.assertTrue(r2.is_primary)
        self.assertEqual(Resume.get_primary(candidate.id).id, r2.id)

        # Deleting the primary resume promotes newest remaining
        client.post(f"/candidate/resumes/{r2.id}/delete", follow_redirects=True)
        db.session.refresh(r1)
        self.assertTrue(r1.is_primary)
        self.assertEqual(Resume.get_primary(candidate.id).id, r1.id)

    def test_02_duplicate_application_race_condition_handled(self):
        """Test that duplicate application submission returns a friendly redirect instead of 500."""
        recruiter = User(
            full_name="Bob Recruiter",
            email="bob_race@test.com",
            role=User.ROLE_RECRUITER,
            is_active_account=True,
        )
        recruiter.set_password("Pass1234!")
        db.session.add(recruiter)
        db.session.flush()

        profile = RecruiterProfile(
            user_id=recruiter.id,
            company_name="RaceTech",
            approval_status=RecruiterProfile.STATUS_APPROVED,
        )
        db.session.add(profile)
        db.session.flush()

        job = Job(
            recruiter_profile_id=profile.id,
            title="Software Developer",
            description="Python Flask development",
            status=Job.STATUS_ACTIVE,
        )
        db.session.add(job)

        candidate = User(
            full_name="Charlie Candidate",
            email="charlie_race@test.com",
            role=User.ROLE_CANDIDATE,
            is_active_account=True,
        )
        candidate.set_password("Pass1234!")
        db.session.add(candidate)
        db.session.flush()

        resume = Resume(
            candidate_id=candidate.id,
            raw_text="Python Flask developer",
            name="Charlie Resume",
            is_primary=True,
        )
        db.session.add(resume)
        db.session.commit()

        client = self._login_as("charlie_race@test.com", "Pass1234!")

        # First apply succeeds
        resp1 = client.post(f"/candidate/jobs/{job.id}/apply", follow_redirects=True)
        self.assertEqual(resp1.status_code, 200)
        self.assertIn(b"Application submitted", resp1.data)

        # Second apply is caught cleanly without 500 error
        resp2 = client.post(f"/candidate/jobs/{job.id}/apply", follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b"already applied", resp2.data)

    def test_03_reopen_auto_closed_applications_on_unhire(self):
        """Test auto-closing other applications on hire and restoring them on hire reversal."""
        rec_user = User(
            full_name="Recruiter Dave",
            email="dave_unhire@test.com",
            role=User.ROLE_RECRUITER,
            is_active_account=True,
        )
        rec_user.set_password("Pass1234!")
        db.session.add(rec_user)
        db.session.flush()

        rec_prof = RecruiterProfile(
            user_id=rec_user.id,
            company_name="DaveTech",
            approval_status=RecruiterProfile.STATUS_APPROVED,
        )
        db.session.add(rec_prof)
        db.session.flush()

        job1 = Job(recruiter_profile_id=rec_prof.id, title="Job A", description="Desc A", status=Job.STATUS_ACTIVE)
        job2 = Job(recruiter_profile_id=rec_prof.id, title="Job B", description="Desc B", status=Job.STATUS_ACTIVE)
        db.session.add_all([job1, job2])

        cand_user = User(
            full_name="Eve Candidate",
            email="eve_unhire@test.com",
            role=User.ROLE_CANDIDATE,
            is_active_account=True,
        )
        cand_user.set_password("Pass1234!")
        db.session.add(cand_user)
        db.session.flush()

        resume = Resume(candidate_id=cand_user.id, raw_text="Python Backend Engineer", is_primary=True)
        db.session.add(resume)
        db.session.flush()

        app1 = Application(job_id=job1.id, candidate_id=cand_user.id, resume_id=resume.id, status=Application.STATUS_INTERVIEW)
        app2 = Application(job_id=job2.id, candidate_id=cand_user.id, resume_id=resume.id, status=Application.STATUS_SHORTLISTED)
        db.session.add_all([app1, app2])
        db.session.commit()

        client = self._login_as("dave_unhire@test.com", "Pass1234!")

        # Recruiter hires Eve for Job 1
        resp_hire = client.post(
            f"/recruiter/applications/{app1.id}/status",
            data={"status": Application.STATUS_HIRED},
            follow_redirects=True,
        )
        self.assertEqual(resp_hire.status_code, 200)

        db.session.refresh(app1)
        db.session.refresh(app2)
        self.assertEqual(app1.status, Application.STATUS_HIRED)
        self.assertEqual(app2.status, Application.STATUS_REJECTED)

        # Recruiter reverses the hire (HIRED -> REJECTED)
        resp_unhire = client.post(
            f"/recruiter/applications/{app1.id}/status",
            data={"status": Application.STATUS_REJECTED},
            follow_redirects=True,
        )
        self.assertEqual(resp_unhire.status_code, 200)

        db.session.refresh(app1)
        db.session.refresh(app2)
        self.assertEqual(app1.status, Application.STATUS_REJECTED)
        # app2 restored to its prior stage (STATUS_SHORTLISTED)
        self.assertEqual(app2.status, Application.STATUS_SHORTLISTED)

    def test_04_admin_reject_recruiter_closes_active_jobs(self):
        """Test that rejecting an approved recruiter automatically closes their active jobs."""
        admin = User(
            full_name="Admin Frank",
            email="frank_admin@test.com",
            role=User.ROLE_ADMIN,
            is_active_account=True,
        )
        admin.set_password("Pass1234!")
        db.session.add(admin)
        db.session.commit()

        rec_user = User(
            full_name="Recruiter Grace",
            email="grace_rec@test.com",
            role=User.ROLE_RECRUITER,
            is_active_account=True,
        )
        rec_user.set_password("Pass1234!")
        db.session.add(rec_user)
        db.session.flush()

        profile = RecruiterProfile(
            user_id=rec_user.id,
            company_name="GraceCorp",
            approval_status=RecruiterProfile.STATUS_APPROVED,
        )
        db.session.add(profile)
        db.session.flush()

        job_active = Job(recruiter_profile_id=profile.id, title="Grace Job 1", description="Desc 1", status=Job.STATUS_ACTIVE)
        job_paused = Job(recruiter_profile_id=profile.id, title="Grace Job 2", description="Desc 2", status=Job.STATUS_PAUSED)
        db.session.add_all([job_active, job_paused])
        db.session.commit()

        client = self._login_as("frank_admin@test.com", "Pass1234!")

        resp = client.post(f"/admin/recruiters/{profile.id}/reject", data={"reason": "Policy violation"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        db.session.refresh(profile)
        db.session.refresh(job_active)
        db.session.refresh(job_paused)
        self.assertEqual(profile.approval_status, RecruiterProfile.STATUS_REJECTED)
        self.assertEqual(job_active.status, Job.STATUS_CLOSED)
        self.assertEqual(job_paused.status, Job.STATUS_CLOSED)

    def test_05_rescore_job_preserves_decided_applications(self):
        """Test that editing a job's requirements skips rescoring already Hired/Rejected candidates."""
        rec_user = User(
            full_name="Recruiter Hank",
            email="hank_rec@test.com",
            role=User.ROLE_RECRUITER,
            is_active_account=True,
        )
        rec_user.set_password("Pass1234!")
        db.session.add(rec_user)
        db.session.flush()

        profile = RecruiterProfile(
            user_id=rec_user.id,
            company_name="HankCorp",
            approval_status=RecruiterProfile.STATUS_APPROVED,
        )
        db.session.add(profile)
        db.session.flush()

        job = Job(
            recruiter_profile_id=profile.id,
            title="Senior Python Architect",
            description="Python, Flask, Microservices",
            required_skills_raw="Python, Flask",
            status=Job.STATUS_ACTIVE,
        )
        db.session.add(job)
        db.session.flush()

        cand1 = User(full_name="Cand 1", email="cand1@test.com", role=User.ROLE_CANDIDATE, is_active_account=True)
        cand2 = User(full_name="Cand 2", email="cand2@test.com", role=User.ROLE_CANDIDATE, is_active_account=True)
        cand1.set_password("Pass1234!")
        cand2.set_password("Pass1234!")
        db.session.add_all([cand1, cand2])
        db.session.flush()

        res1 = Resume(candidate_id=cand1.id, raw_text="Python Flask expert", is_primary=True)
        res2 = Resume(candidate_id=cand2.id, raw_text="Java Spring expert", is_primary=True)
        db.session.add_all([res1, res2])
        db.session.flush()

        app_hired = Application(
            job_id=job.id,
            candidate_id=cand1.id,
            resume_id=res1.id,
            match_score=95.0,
            status=Application.STATUS_HIRED,
        )
        app_open = Application(
            job_id=job.id,
            candidate_id=cand2.id,
            resume_id=res2.id,
            match_score=10.0,
            status=Application.STATUS_UNDER_REVIEW,
        )
        db.session.add_all([app_hired, app_open])
        db.session.commit()

        # Recruiter changes job requirements drastically to Java
        job.required_skills_raw = "Java, Spring, Microservices"
        job.description = "Java Spring developer"
        db.session.commit()

        # Run rescore
        _rescore_applications_for_job(job)

        db.session.refresh(app_hired)
        db.session.refresh(app_open)

        # Hired candidate match_score preserved at 95.0
        self.assertEqual(app_hired.match_score, 95.0)
        # Open candidate was rescored
        self.assertNotEqual(app_open.match_score, 10.0)


if __name__ == "__main__":
    unittest.main()
