"""Test Suite for Application Deadline & Job Details Action Buttons."""

import unittest
from datetime import timedelta
from app.utils.time import utcnow
from app import create_app, db
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.application import Application
from app.models.recruiter_profile import RecruiterProfile


class TestJobDeadline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()

        # Recruiter
        cls.recruiter_user = User(
            full_name="Recruiter One",
            email="recruiter_deadline@example.com",
            role=User.ROLE_RECRUITER,
            is_active_account=True,
        )
        cls.recruiter_user.set_password("Recruiter@1234")
        db.session.add(cls.recruiter_user)
        db.session.flush()

        cls.rec_profile = RecruiterProfile(
            user_id=cls.recruiter_user.id,
            company_name="DeadlineTech",
            approval_status=RecruiterProfile.STATUS_APPROVED,
        )
        db.session.add(cls.rec_profile)

        # Candidate
        cls.candidate_user = User(
            full_name="Candidate One",
            email="candidate_deadline@example.com",
            role=User.ROLE_CANDIDATE,
            is_active_account=True,
        )
        cls.candidate_user.set_password("Candidate@1234")
        db.session.add(cls.candidate_user)
        db.session.flush()

        # Resume for candidate
        cls.resume = Resume(
            candidate_id=cls.candidate_user.id,
            raw_text="Python Flask PostgreSQL developer with 4 years experience",
            target_role="Senior Python Dev",
        )
        db.session.add(cls.resume)
        db.session.commit()

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

    def test_01_job_model_deadline_properties(self):
        """Test is_deadline_passed and is_accepting_applications helper properties."""
        future_deadline = utcnow() + timedelta(days=7)
        past_deadline = utcnow() - timedelta(days=1)

        job_open = Job(
            recruiter_profile_id=self.rec_profile.id,
            title="Open Engineer",
            description="Looking for Python engineers",
            status=Job.STATUS_ACTIVE,
            application_deadline=future_deadline,
        )
        job_expired = Job(
            recruiter_profile_id=self.rec_profile.id,
            title="Expired Engineer",
            description="Looking for Python engineers",
            status=Job.STATUS_ACTIVE,
            application_deadline=past_deadline,
        )
        job_no_deadline = Job(
            recruiter_profile_id=self.rec_profile.id,
            title="No Deadline Engineer",
            description="Looking for Python engineers",
            status=Job.STATUS_ACTIVE,
            application_deadline=None,
        )

        db.session.add_all([job_open, job_expired, job_no_deadline])
        db.session.commit()

        self.assertFalse(job_open.is_deadline_passed)
        self.assertTrue(job_open.is_accepting_applications)

        self.assertTrue(job_expired.is_deadline_passed)
        self.assertFalse(job_expired.is_accepting_applications)

        self.assertFalse(job_no_deadline.is_deadline_passed)
        self.assertTrue(job_no_deadline.is_accepting_applications)

    def test_02_candidate_can_apply_before_deadline(self):
        """Candidate can apply to active job before the deadline."""
        future_deadline = utcnow() + timedelta(days=5)
        job = Job(
            recruiter_profile_id=self.rec_profile.id,
            title="Active Job Before Deadline",
            description="Python backend developer needed.",
            status=Job.STATUS_ACTIVE,
            application_deadline=future_deadline,
        )
        db.session.add(job)
        db.session.commit()

        client = self._login_as("candidate_deadline@example.com", "Candidate@1234")
        resp = client.post(f"/candidate/jobs/{job.id}/apply", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Application submitted", resp.data)

        # Check application recorded
        app = Application.query.filter_by(job_id=job.id, candidate_id=self.candidate_user.id).first()
        self.assertIsNotNone(app)

    def test_03_candidate_cannot_apply_after_deadline(self):
        """Candidate application rejected server-side when deadline has passed."""
        past_deadline = utcnow() - timedelta(hours=2)
        job = Job(
            recruiter_profile_id=self.rec_profile.id,
            title="Expired Job Apply Attempt",
            description="Python backend developer needed.",
            status=Job.STATUS_ACTIVE,
            application_deadline=past_deadline,
        )
        db.session.add(job)
        db.session.commit()

        client = self._login_as("candidate_deadline@example.com", "Candidate@1234")
        resp = client.post(f"/candidate/jobs/{job.id}/apply", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"application deadline for this job has passed", resp.data)

        # Confirm no application record was created
        app = Application.query.filter_by(job_id=job.id, candidate_id=self.candidate_user.id).first()
        self.assertIsNone(app)

    def test_04_recruiter_can_extend_deadline_to_reopen(self):
        """Recruiter changing deadline to a future date reopens applications."""
        past_deadline = utcnow() - timedelta(days=2)
        job = Job(
            recruiter_profile_id=self.rec_profile.id,
            title="Reopening Job",
            description="Python backend developer needed.",
            status=Job.STATUS_ACTIVE,
            application_deadline=past_deadline,
        )
        db.session.add(job)
        db.session.commit()

        # Currently expired
        self.assertFalse(job.is_accepting_applications)

        # Extend deadline to future
        new_future = utcnow() + timedelta(days=10)
        job.application_deadline = new_future
        db.session.commit()

        # Now accepting applications again
        self.assertTrue(job.is_accepting_applications)

    def test_05_job_details_page_renders_deadline_and_buttons(self):
        """Job detail page renders buttons in top-right and shows deadline info."""
        future_deadline = utcnow() + timedelta(days=3)
        job = Job(
            recruiter_profile_id=self.rec_profile.id,
            title="UI Check Job",
            description="Frontend developer with React and Tailwind.",
            status=Job.STATUS_ACTIVE,
            application_deadline=future_deadline,
        )
        db.session.add(job)
        db.session.commit()

        anon_client = self.app.test_client()
        # Anonymous view
        resp = anon_client.get(f"/jobs/{job.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Log in to apply", resp.data)
        self.assertIn(b"Application Deadline", resp.data)

        # Candidate view
        candidate_client = self._login_as("candidate_deadline@example.com", "Candidate@1234")
        resp = candidate_client.get(f"/jobs/{job.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Apply now", resp.data)
        self.assertIn(b"Save job", resp.data)


if __name__ == "__main__":
    unittest.main()
