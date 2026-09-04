"""Tests for the two Phase 4 pipeline decisions.

1. Marking an application HIRED auto-closes the same candidate's other
   still-open applications (any job, any recruiter) — see
   _auto_close_other_applications_on_hire() in recruiter/routes.py.
2. A closed job freezes pipeline actions — the only status change still
   allowed on it is moving an application to REJECTED.

Both are exercised through the real single-update and bulk-update routes,
since the whole point of this audit thread has been keeping those two
routes in lockstep.
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


class TestPipelineBusinessRules(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()

        deadline = utcnow() + timedelta(days=30)

        # Two independent recruiters/companies, so "other recruiters" is
        # genuinely tested, not just "other jobs from the same recruiter".
        cls.recruiter_1 = User(full_name="Recruiter One", email="rules_recruiter1@example.com",
                                role=User.ROLE_RECRUITER, is_active_account=True)
        cls.recruiter_1.set_password("Recruiter@1234")
        cls.recruiter_2 = User(full_name="Recruiter Two", email="rules_recruiter2@example.com",
                                role=User.ROLE_RECRUITER, is_active_account=True)
        cls.recruiter_2.set_password("Recruiter@1234")
        db.session.add_all([cls.recruiter_1, cls.recruiter_2])
        db.session.flush()

        cls.profile_1 = RecruiterProfile(user_id=cls.recruiter_1.id, company_name="CompanyOne",
                                          approval_status=RecruiterProfile.STATUS_APPROVED)
        cls.profile_2 = RecruiterProfile(user_id=cls.recruiter_2.id, company_name="CompanyTwo",
                                          approval_status=RecruiterProfile.STATUS_APPROVED)
        db.session.add_all([cls.profile_1, cls.profile_2])
        db.session.flush()

        cls.job_1 = Job(recruiter_profile_id=cls.profile_1.id, title="Job One",
                         description="First job.", required_skills_raw="Python",
                         status=Job.STATUS_ACTIVE, application_deadline=deadline)
        cls.job_2 = Job(recruiter_profile_id=cls.profile_2.id, title="Job Two",
                         description="Second job, different company.", required_skills_raw="Python",
                         status=Job.STATUS_ACTIVE, application_deadline=deadline)
        cls.job_3 = Job(recruiter_profile_id=cls.profile_1.id, title="Job Three",
                         description="Third job, will be closed.", required_skills_raw="Python",
                         status=Job.STATUS_ACTIVE, application_deadline=deadline)
        db.session.add_all([cls.job_1, cls.job_2, cls.job_3])
        db.session.commit()

        cls.job_1_id, cls.job_2_id, cls.job_3_id = cls.job_1.id, cls.job_2.id, cls.job_3.id

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

    def _make_candidate(self, tag):
        candidate = User(full_name=f"Candidate {tag}", email=f"rules_candidate_{tag}@example.com",
                          role=User.ROLE_CANDIDATE, is_active_account=True, public_slug=f"rules-candidate-{tag}")
        candidate.set_password("Candidate@1234")
        db.session.add(candidate)
        db.session.flush()
        resume = Resume(candidate_id=candidate.id, source="paste", raw_text="Python developer.")
        db.session.add(resume)
        db.session.flush()
        return candidate, resume

    def _make_application(self, job_id, candidate_id, resume_id, status):
        application = Application(job_id=job_id, candidate_id=candidate_id, resume_id=resume_id,
                                   match_score=50, status=status)
        db.session.add(application)
        db.session.commit()
        return application.id

    # --- Decision 1: hiring auto-closes the candidate's other open applications ---

    def test_hiring_auto_rejects_open_applications_on_other_jobs_and_recruiters(self):
        candidate, resume = self._make_candidate("hire1")
        app_target_id = self._make_application(self.job_1_id, candidate.id, resume.id, Application.STATUS_INTERVIEW)
        app_other_company_id = self._make_application(self.job_2_id, candidate.id, resume.id, Application.STATUS_SHORTLISTED)
        app_other_job_same_recruiter_id = self._make_application(self.job_3_id, candidate.id, resume.id, Application.STATUS_APPLIED)

        client = self._login("rules_recruiter1@example.com", "Recruiter@1234")
        resp = client.post(
            f"/recruiter/applications/{app_target_id}/status",
            data={"status": Application.STATUS_HIRED},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)

        db.session.expire_all()
        self.assertEqual(db.session.get(Application, app_target_id).status, Application.STATUS_HIRED)
        self.assertEqual(db.session.get(Application, app_other_company_id).status, Application.STATUS_REJECTED)
        self.assertEqual(db.session.get(Application, app_other_job_same_recruiter_id).status, Application.STATUS_REJECTED)

        auto_event = (
            ApplicationEvent.query.filter_by(application_id=app_other_company_id)
            .order_by(ApplicationEvent.id.desc()).first()
        )
        self.assertIn("hired for a different role", auto_event.note.lower())

    def test_hiring_does_not_touch_already_hired_or_rejected_applications(self):
        candidate, resume = self._make_candidate("hire2")
        app_target_id = self._make_application(self.job_1_id, candidate.id, resume.id, Application.STATUS_INTERVIEW)
        already_rejected_id = self._make_application(self.job_2_id, candidate.id, resume.id, Application.STATUS_REJECTED)

        other_candidate, other_resume = self._make_candidate("hire2b")
        already_hired_elsewhere_id = self._make_application(self.job_3_id, other_candidate.id, other_resume.id, Application.STATUS_HIRED)

        client = self._login("rules_recruiter1@example.com", "Recruiter@1234")
        client.post(f"/recruiter/applications/{app_target_id}/status", data={"status": Application.STATUS_HIRED}, follow_redirects=True)

        db.session.expire_all()
        # Already-terminal application for the SAME candidate is untouched (no duplicate event/status churn).
        self.assertEqual(db.session.get(Application, already_rejected_id).status, Application.STATUS_REJECTED)
        # A different candidate's already-hired application is completely unaffected.
        self.assertEqual(db.session.get(Application, already_hired_elsewhere_id).status, Application.STATUS_HIRED)

    def test_bulk_hire_also_auto_closes_other_applications(self):
        candidate, resume = self._make_candidate("hire3")
        app_target_id = self._make_application(self.job_1_id, candidate.id, resume.id, Application.STATUS_INTERVIEW)
        app_other_id = self._make_application(self.job_2_id, candidate.id, resume.id, Application.STATUS_APPLIED)

        client = self._login("rules_recruiter1@example.com", "Recruiter@1234")
        client.post(
            f"/recruiter/jobs/{self.job_1_id}/applicants/bulk-status",
            data={"status": Application.STATUS_HIRED, "application_ids": [str(app_target_id)]},
            follow_redirects=True,
        )

        db.session.expire_all()
        self.assertEqual(db.session.get(Application, app_target_id).status, Application.STATUS_HIRED)
        self.assertEqual(db.session.get(Application, app_other_id).status, Application.STATUS_REJECTED)

    # --- Decision 2: closed jobs freeze pipeline actions except rejecting ---

    def test_closed_job_blocks_progression_on_single_update_route(self):
        candidate, resume = self._make_candidate("closed1")
        app_id = self._make_application(self.job_3_id, candidate.id, resume.id, Application.STATUS_INTERVIEW)

        client = self._login("rules_recruiter1@example.com", "Recruiter@1234")
        client.post(f"/recruiter/jobs/{self.job_3_id}/close", follow_redirects=True)

        resp = client.post(f"/recruiter/applications/{app_id}/status", data={"status": Application.STATUS_HIRED}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        db.session.expire_all()
        self.assertEqual(db.session.get(Application, app_id).status, Application.STATUS_INTERVIEW)

    def test_closed_job_still_allows_rejecting_on_single_update_route(self):
        candidate, resume = self._make_candidate("closed2")
        app_id = self._make_application(self.job_3_id, candidate.id, resume.id, Application.STATUS_INTERVIEW)

        client = self._login("rules_recruiter1@example.com", "Recruiter@1234")
        client.post(f"/recruiter/jobs/{self.job_3_id}/close", follow_redirects=True)

        resp = client.post(f"/recruiter/applications/{app_id}/status", data={"status": Application.STATUS_REJECTED}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        db.session.expire_all()
        self.assertEqual(db.session.get(Application, app_id).status, Application.STATUS_REJECTED)

    def test_closed_job_blocks_bulk_progression_but_allows_bulk_rejection(self):
        candidate, resume = self._make_candidate("closed3")
        app_id = self._make_application(self.job_3_id, candidate.id, resume.id, Application.STATUS_SHORTLISTED)

        client = self._login("rules_recruiter1@example.com", "Recruiter@1234")
        client.post(f"/recruiter/jobs/{self.job_3_id}/close", follow_redirects=True)

        resp = client.post(
            f"/recruiter/jobs/{self.job_3_id}/applicants/bulk-status",
            data={"status": Application.STATUS_INTERVIEW, "application_ids": [str(app_id)]},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        db.session.expire_all()
        self.assertEqual(db.session.get(Application, app_id).status, Application.STATUS_SHORTLISTED)

        resp = client.post(
            f"/recruiter/jobs/{self.job_3_id}/applicants/bulk-status",
            data={"status": Application.STATUS_REJECTED, "application_ids": [str(app_id)]},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        db.session.expire_all()
        self.assertEqual(db.session.get(Application, app_id).status, Application.STATUS_REJECTED)

    def test_reopening_a_job_restores_normal_pipeline_actions(self):
        candidate, resume = self._make_candidate("closed4")
        app_id = self._make_application(self.job_3_id, candidate.id, resume.id, Application.STATUS_INTERVIEW)

        client = self._login("rules_recruiter1@example.com", "Recruiter@1234")
        client.post(f"/recruiter/jobs/{self.job_3_id}/close", follow_redirects=True)
        client.post(f"/recruiter/jobs/{self.job_3_id}/reopen", follow_redirects=True)

        resp = client.post(f"/recruiter/applications/{app_id}/status", data={"status": Application.STATUS_HIRED}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        db.session.expire_all()
        self.assertEqual(db.session.get(Application, app_id).status, Application.STATUS_HIRED)


if __name__ == "__main__":
    unittest.main()
