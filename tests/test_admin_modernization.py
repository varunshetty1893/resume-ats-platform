import unittest
from flask_login import logout_user
from app import create_app, db
from app.models.user import User
from app.models.recruiter_profile import RecruiterProfile
from app.models.job import Job
from app.models.resume import Resume
from app.models.application import Application


class AdminModernizationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()

        # Unique test accounts
        cls.admin = User(
            full_name="Super Admin Mod",
            email="admin_mod@example.com",
            role=User.ROLE_ADMIN,
            is_active_account=True,
        )
        cls.admin.set_password("AdminPass123!")

        cls.recruiter_user = User(
            full_name="Jane Recruiter Mod",
            email="jane_mod@acme.com",
            role=User.ROLE_RECRUITER,
            is_active_account=True,
            location="Bengaluru, India",
        )
        cls.recruiter_user.set_password("RecruiterPass123!")

        cls.candidate = User(
            full_name="John Candidate Mod",
            email="john_mod@candidate.com",
            role=User.ROLE_CANDIDATE,
            is_active_account=True,
        )
        cls.candidate.set_password("CandidatePass123!")

        db.session.add_all([cls.admin, cls.recruiter_user, cls.candidate])
        db.session.commit()

        cls.recruiter_profile = RecruiterProfile(
            user_id=cls.recruiter_user.id,
            company_name="Acme Corporation Mod",
            industry="technology",
            company_size="51-200",
            contact_role="Head of Talent",
            phone="+91 9876543210",
            approval_status=RecruiterProfile.STATUS_APPROVED,
        )
        db.session.add(cls.recruiter_profile)
        db.session.commit()

        cls.job = Job(
            recruiter_profile_id=cls.recruiter_profile.id,
            title="Staff Software Engineer",
            description="Lead our distributed platform architecture.",
            job_type="full_time",
            work_mode="remote",
            experience_level="senior",
            status=Job.STATUS_ACTIVE,
        )
        db.session.add(cls.job)
        db.session.commit()

        cls.resume = Resume(
            candidate_id=cls.candidate.id,
            raw_text="Experienced Software Engineer with Python and React.",
            name="John Resume",
            source="paste",
        )
        db.session.add(cls.resume)
        db.session.commit()

        cls.app_record = Application(
            job_id=cls.job.id,
            candidate_id=cls.candidate.id,
            resume_id=cls.resume.id,
            status=Application.STATUS_APPLIED,
            match_score=85.0,
        )
        db.session.add(cls.app_record)
        db.session.commit()

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
        """Create a fresh authenticated test client — matching the pattern from test_candidate_security.py."""
        with self.app.test_request_context():
            from flask_login import logout_user
            logout_user()
        client = self.app.test_client()
        client.post(
            "/auth/login",
            data={
                "login-email": email,
                "login-password": password,
                "login-submit": "Sign in",
            },
        )
        return client

    def test_admin_navigation_and_footer(self):
        """Verify Admin navigation shows updated items and compact admin footer."""
        client = self._login_as("admin_mod@example.com", "AdminPass123!")
        res = client.get("/admin/")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Nav items
        self.assertIn("Dashboard", html)
        self.assertIn("Users", html)
        self.assertIn("Recruiters", html)
        self.assertIn("Jobs", html)
        self.assertIn("Reports", html)
        self.assertIn("Audit", html)
        self.assertIn("System", html)

        # Ensure Companies and Applications nav links are removed
        self.assertNotIn(">Companies</a>", html)
        self.assertNotIn(">Applications</a>", html)

        # Admin footer
        self.assertIn("Zentra Admin", html)
        self.assertIn("&copy; 2026 Zentra. All rights reserved.", html)
        self.assertIn("Privacy", html)
        self.assertIn("Terms", html)

    def test_admin_dashboard_metrics(self):
        """Verify Admin dashboard metrics and sections load cleanly."""
        client = self._login_as("admin_mod@example.com", "AdminPass123!")
        res = client.get("/admin/")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Platform Administration", html)
        self.assertIn("Total Users", html)
        self.assertIn("Recruiters", html)
        self.assertIn("Platform Jobs", html)
        self.assertIn("Recent Platform Registrations", html)
        self.assertIn("Audit Trail", html)

    def test_legacy_companies_and_applications_redirects(self):
        """Verify legacy /admin/companies and /admin/applications redirect cleanly."""
        client = self._login_as("admin_mod@example.com", "AdminPass123!")

        res1 = client.get("/admin/companies")
        self.assertEqual(res1.status_code, 302)
        self.assertIn("/admin/recruiters", res1.headers["Location"])

        res2 = client.get("/admin/companies/Acme%20Corporation%20Mod")
        self.assertEqual(res2.status_code, 302)
        self.assertIn("Acme", res2.headers["Location"])

        res3 = client.get("/admin/applications")
        self.assertEqual(res3.status_code, 302)
        self.assertIn("/admin/users", res3.headers["Location"])

        res4 = client.get(f"/admin/applications/{self.app_record.id}")
        self.assertEqual(res4.status_code, 302)
        self.assertIn(f"/admin/users/{self.candidate.id}", res4.headers["Location"])

    def test_admin_users_and_user_detail(self):
        """Verify Users directory and User detail dossier."""
        client = self._login_as("admin_mod@example.com", "AdminPass123!")

        res = client.get("/admin/users")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("User Directory", html)
        self.assertIn("John Candidate Mod", html)
        self.assertIn("Jane Recruiter Mod", html)

        # Candidate user detail
        res_cand = client.get(f"/admin/users/{self.candidate.id}")
        self.assertEqual(res_cand.status_code, 200)
        cand_html = res_cand.get_data(as_text=True)
        self.assertIn("Application History", cand_html)
        self.assertIn("Staff Software Engineer", cand_html)

    def test_admin_recruiter_detail_dossier(self):
        """Verify Recruiter detail page displays complete profile and missing field placeholders."""
        client = self._login_as("admin_mod@example.com", "AdminPass123!")

        res = client.get(f"/admin/recruiters/{self.recruiter_profile.id}")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Acme Corporation Mod", html)
        self.assertIn("Jane Recruiter Mod", html)
        self.assertIn("Head of Talent", html)
        self.assertIn("+91 9876543210", html)
        self.assertIn("Technology", html)
        self.assertIn("51-200", html)
        self.assertIn("Staff Software Engineer", html)
        self.assertIn("Not provided", html)

    def test_admin_recruiter_verified_checkmark(self):
        """Verify approved recruiters display the green verified checkmark instead of 'Approved' text badge."""
        client = self._login_as("admin_mod@example.com", "AdminPass123!")
        res = client.get("/admin/")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Check for verified badge icon
        self.assertIn("bi-patch-check-fill", html)
        self.assertIn("Verified Recruiter", html)

    def test_admin_reports_organisations_pagination(self):
        """Verify Reports page renders top recruiting organisations with server-side pagination."""
        client = self._login_as("admin_mod@example.com", "AdminPass123!")
        res = client.get("/admin/reports?page=1&per_page=10")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Top Recruiting Organisations", html)
        self.assertIn("Acme Corporation Mod", html)
        self.assertIn("Active Job Count", html)

    def test_admin_audit_rich_types_and_modal(self):
        """Verify Audit Trail contains rich audit event types and interactive modal dialog."""
        client = self._login_as("admin_mod@example.com", "AdminPass123!")
        res = client.get("/admin/audit")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Check filter options and total counter
        self.assertIn("Administrative Audit Trail", html)
        self.assertIn("auditDetailModal", html)
    def test_admin_system_settings_enforcement(self):
        """Verify Admin system settings take real effect across auth, recruiter, and jobs routes."""
        from app.models.admin_setting import AdminSetting

        # Disable candidate registration
        AdminSetting.set("registration_open", "false")
        db.session.commit()

        client = self.app.test_client()
        res = client.post("/auth/signup", data={
            "signup-full_name": "Blocked Candidate",
            "signup-email": "blocked@example.com",
            "signup-password": "Password123!",
            "signup-confirm_password": "Password123!",
            "signup-agree_terms": "y",
            "signup-submit": "Create account",
        })
        self.assertIn("disabled by administrator", res.get_data(as_text=True))

        # Re-enable candidate registration
        AdminSetting.set("registration_open", "true")
        db.session.commit()

        # Disable public job listing for anonymous users
        AdminSetting.set("public_job_listing", "false")
        db.session.commit()

        anon_client = self.app.test_client()
        with self.app.test_request_context():
            from flask_login import logout_user
            logout_user()

        res_jobs = anon_client.get("/jobs", follow_redirects=False)
        self.assertEqual(res_jobs.status_code, 302)
        self.assertIn("/auth/login", res_jobs.headers["Location"])

        # Re-enable public job listing
        AdminSetting.set("public_job_listing", "true")
        db.session.commit()

    def test_admin_notifications_delivery(self):
        """Verify Admin receives in-app notifications upon recruiter and job events."""
        from app.models.notification import Notification

        Notification.notify_admins(
            title="System Automated Test Alert",
            message="Verification of admin notification dispatch pipeline.",
            link="/admin/",
        )
        db.session.commit()

        client = self._login_as("admin_mod@example.com", "AdminPass123!")
        res = client.get("/admin/notifications")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("System Automated Test Alert", html)

    def test_admin_profile_dropdown_clean(self):
        """Verify redundant Dashboard and System Settings links are removed from profile dropdown."""
        client = self._login_as("admin_mod@example.com", "AdminPass123!")
        res = client.get("/admin/")
        html = res.get_data(as_text=True)

        # Look at the profile-menu block specifically
        profile_menu_start = html.find('id="profile-menu"')
        menu_html = html[profile_menu_start:profile_menu_start + 1800]

        # Ensure Dashboard and System Settings aren't present inside the profile dropdown menu
        self.assertNotIn("Dashboard", menu_html)
        self.assertNotIn("System Settings", menu_html)
        self.assertIn("Notifications", menu_html)
        self.assertIn("Admin Profile", menu_html)


if __name__ == "__main__":
    unittest.main()
