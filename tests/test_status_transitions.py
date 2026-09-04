"""APPLICATION_VALID_TRANSITIONS parity tests.

Before the shared-map fix (see the recruiter/routes.py audit note),
update_application_status() (single-candidate control) and
bulk_update_applicant_status() enforced status transitions with two
separately-maintained rule sets that could silently drift apart. This
suite makes that divergence structurally impossible to reintroduce: for
every (from_status, to_status) pair across every status, it drives both
routes through the real Flask test client and asserts they agree —
allow together, or reject together — using the same
APPLICATION_VALID_TRANSITIONS map both routes are supposed to read from.
"""

import unittest

from app import create_app, db
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.application import Application
from app.models.recruiter_profile import RecruiterProfile
from app.recruiter.routes import APPLICATION_VALID_TRANSITIONS


class TestStatusTransitionParity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()

        cls.recruiter_user = User(
            full_name="Transition Recruiter",
            email="transitions_recruiter@example.com",
            role=User.ROLE_RECRUITER,
            is_active_account=True,
        )
        cls.recruiter_user.set_password("Recruiter@1234")
        db.session.add(cls.recruiter_user)
        db.session.flush()

        cls.rec_profile = RecruiterProfile(
            user_id=cls.recruiter_user.id,
            company_name="TransitionCorp",
            approval_status=RecruiterProfile.STATUS_APPROVED,
        )
        db.session.add(cls.rec_profile)
        db.session.flush()

        cls.job = Job(
            recruiter_profile_id=cls.rec_profile.id,
            title="Transition Test Role",
            description="Role used purely to drive status-transition tests.",
            required_skills_raw="Python",
            status=Job.STATUS_ACTIVE,
        )
        db.session.add(cls.job)

        cls.candidate = User(
            full_name="Transition Candidate",
            email="transitions_candidate@example.com",
            role=User.ROLE_CANDIDATE,
            is_active_account=True,
            public_slug="transitions-candidate",
        )
        cls.candidate.set_password("Candidate@1234")
        db.session.add(cls.candidate)
        db.session.flush()

        cls.resume = Resume(candidate_id=cls.candidate.id, source="paste", raw_text="Python developer.")
        db.session.add(cls.resume)
        db.session.flush()

        # A single reusable Application row — (job_id, candidate_id) is
        # unique, so each combo resets this row's status directly rather
        # than inserting a fresh row per combo.
        cls.application = Application(
            job_id=cls.job.id,
            candidate_id=cls.candidate.id,
            resume_id=cls.resume.id,
            match_score=50,
            status=Application.STATUS_APPLIED,
        )
        db.session.add(cls.application)
        db.session.commit()

        cls.job_id = cls.job.id
        cls.candidate_id = cls.candidate.id
        cls.resume_id = cls.resume.id
        cls.application_id = cls.application.id

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

    def _login_as_recruiter(self):
        with self.app.test_request_context():
            from flask_login import logout_user
            logout_user()
        client = self.app.test_client()
        client.post(
            "/auth/login",
            data={
                "login-email": "transitions_recruiter@example.com",
                "login-password": "Recruiter@1234",
                "login-submit": "Log in",
            },
        )
        return client

    def _reset_application_status(self, from_status):
        application = db.session.get(Application, self.application_id)
        application.status = from_status
        db.session.commit()
        return self.application_id

    def _is_allowed(self, from_status, to_status):
        return to_status == from_status or to_status in APPLICATION_VALID_TRANSITIONS.get(from_status, [])

    def test_every_transition_pair_agrees_between_single_and_bulk_routes(self):
        client = self._login_as_recruiter()

        for from_status in Application.STATUSES:
            for to_status in Application.STATUSES:
                expected_allowed = self._is_allowed(from_status, to_status)

                with self.subTest(route="single", frm=from_status, to=to_status):
                    app_id = self._reset_application_status(from_status)
                    client.post(
                        f"/recruiter/applications/{app_id}/status",
                        data={"status": to_status},
                        follow_redirects=True,
                    )
                    actual_status = db.session.get(Application, app_id).status
                    if expected_allowed:
                        self.assertEqual(
                            actual_status, to_status,
                            f"single-update route should allow {from_status} -> {to_status}"
                        )
                    else:
                        self.assertEqual(
                            actual_status, from_status,
                            f"single-update route should reject {from_status} -> {to_status}, "
                            f"but the application moved to '{actual_status}'"
                        )

                with self.subTest(route="bulk", frm=from_status, to=to_status):
                    app_id = self._reset_application_status(from_status)
                    client.post(
                        f"/recruiter/jobs/{self.job_id}/applicants/bulk-status",
                        data={"status": to_status, "application_ids": [str(app_id)]},
                        follow_redirects=True,
                    )
                    actual_status = db.session.get(Application, app_id).status
                    if expected_allowed:
                        self.assertEqual(
                            actual_status, to_status,
                            f"bulk-update route should allow {from_status} -> {to_status}"
                        )
                    else:
                        self.assertEqual(
                            actual_status, from_status,
                            f"bulk-update route should reject {from_status} -> {to_status}, "
                            f"but the application moved to '{actual_status}'"
                        )

    def test_transition_map_has_no_self_loops(self):
        """Every status's allowed-transitions list should only contain *other*
        statuses — a status transitioning "to itself" is handled separately
        (both routes treat new_status == current status as always allowed,
        independent of this map), so a self-loop here would be redundant
        and could mask a copy-paste mistake between two adjacent entries."""
        for status, targets in APPLICATION_VALID_TRANSITIONS.items():
            self.assertNotIn(status, targets, f"{status} lists itself as a valid transition target")

    def test_every_status_is_covered_by_the_transition_map(self):
        """Every value in Application.STATUSES should have an entry in
        APPLICATION_VALID_TRANSITIONS (even if its list is empty) — a
        missing key falls back to .get(status, []), which silently means
        "no transitions allowed" and would be easy to miss if a new status
        is ever added without updating the map."""
        for status in Application.STATUSES:
            self.assertIn(status, APPLICATION_VALID_TRANSITIONS, f"{status} has no entry in APPLICATION_VALID_TRANSITIONS")


if __name__ == "__main__":
    unittest.main()
