"""Test Suite for Zentra Help & Support Ticket System."""

import unittest
from app import create_app, db
from app.models.user import User
from app.models.support_ticket import SupportTicket, SupportTicketMessage
from app.models.notification import Notification
from app.models.recruiter_profile import RecruiterProfile


class TestSupportSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()

        # 1. Create Admin
        cls.admin_user = User(
            full_name="Platform Admin",
            email="admin_support@example.com",
            role=User.ROLE_ADMIN,
            is_active_account=True,
        )
        cls.admin_user.set_password("Admin@1234")
        db.session.add(cls.admin_user)

        # 2. Create Candidate A
        cls.candidate_a = User(
            full_name="Alice Candidate",
            email="alice_support@example.com",
            role=User.ROLE_CANDIDATE,
            is_active_account=True,
        )
        cls.candidate_a.set_password("Alice@1234")
        db.session.add(cls.candidate_a)

        # 3. Create Candidate B
        cls.candidate_b = User(
            full_name="Bob Candidate",
            email="bob_support@example.com",
            role=User.ROLE_CANDIDATE,
            is_active_account=True,
        )
        cls.candidate_b.set_password("Bob@1234")
        db.session.add(cls.candidate_b)

        # 4. Create Recruiter
        cls.recruiter_user = User(
            full_name="Rachel Recruiter",
            email="rachel_support@example.com",
            role=User.ROLE_RECRUITER,
            is_active_account=True,
        )
        cls.recruiter_user.set_password("Recruiter@1234")
        db.session.add(cls.recruiter_user)
        db.session.flush()

        cls.rec_profile = RecruiterProfile(
            user_id=cls.recruiter_user.id,
            company_name="SupportCorp",
            approval_status=RecruiterProfile.STATUS_APPROVED,
        )
        db.session.add(cls.rec_profile)
        db.session.commit()

        cls.admin_id = cls.admin_user.id
        cls.alice_id = cls.candidate_a.id
        cls.bob_id = cls.candidate_b.id
        cls.recruiter_id = cls.recruiter_user.id

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

    def test_01_candidate_can_create_ticket_and_notifies_admin(self):
        """Candidate submits a support ticket and an in-app notification is sent to admins."""
        client = self._login_as("alice_support@example.com", "Alice@1234")

        initial_admin_notifs = Notification.query.filter_by(candidate_id=self.admin_id).count()

        resp = client.post(
            "/support/new",
            data={
                "issue_type": SupportTicket.ISSUE_RESUME_ATS,
                "subject": "ATS Scoring Calculation Question",
                "description": "I need help understanding why my skills score was 60% on python role.",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"ATS Scoring Calculation Question", resp.data)

        # Check ticket in database
        ticket = SupportTicket.query.filter_by(user_id=self.alice_id, subject="ATS Scoring Calculation Question").first()
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.status, SupportTicket.STATUS_OPEN)
        self.assertEqual(len(ticket.messages), 1)

        # Check admin received notification
        new_admin_notifs = Notification.query.filter_by(candidate_id=self.admin_id).count()
        self.assertEqual(new_admin_notifs, initial_admin_notifs + 1)
        latest_notif = Notification.query.filter_by(candidate_id=self.admin_id).order_by(Notification.created_at.desc()).first()
        self.assertIn(f"#{ticket.id}", latest_notif.title)
        self.assertIn(f"/admin/support/{ticket.id}", latest_notif.link)

    def test_02_recruiter_can_create_ticket(self):
        """Recruiter submits a support ticket with job_posting issue type."""
        client = self._login_as("rachel_support@example.com", "Recruiter@1234")

        resp = client.post(
            "/support/new",
            data={
                "issue_type": SupportTicket.ISSUE_JOB_POSTING,
                "subject": "Need help extending job deadline",
                "description": "How do I extend the deadline for our Senior Backend position?",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Need help extending job deadline", resp.data)

        ticket = SupportTicket.query.filter_by(user_id=self.recruiter_id, subject="Need help extending job deadline").first()
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.status, SupportTicket.STATUS_OPEN)

    def test_03_idor_isolation_between_candidates(self):
        """Candidate Bob cannot view Candidate Alice's ticket."""
        ticket_alice = SupportTicket(
            user_id=self.alice_id,
            issue_type=SupportTicket.ISSUE_ACCOUNT,
            subject="Alice Private Ticket",
            description="Private inquiry from Alice",
            status=SupportTicket.STATUS_OPEN,
        )
        db.session.add(ticket_alice)
        db.session.commit()

        # Bob logs in and tries to access Alice's ticket
        bob_client = self._login_as("bob_support@example.com", "Bob@1234")
        resp = bob_client.get(f"/support/{ticket_alice.id}")
        self.assertEqual(resp.status_code, 404)

        # Alice logs in and can access her ticket
        alice_client = self._login_as("alice_support@example.com", "Alice@1234")
        resp = alice_client.get(f"/support/{ticket_alice.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Alice Private Ticket", resp.data)

    def test_04_admin_can_list_filter_and_search_tickets(self):
        """Admin can list, search, and filter tickets by role and status."""
        admin_client = self._login_as("admin_support@example.com", "Admin@1234")

        # Basic listing
        resp = admin_client.get("/admin/support")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Support Tickets", resp.data)

        # Filter by candidate role
        resp = admin_client.get("/admin/support?role=candidate")
        self.assertEqual(resp.status_code, 200)

        # Filter by status open
        resp = admin_client.get("/admin/support?status=open")
        self.assertEqual(resp.status_code, 200)

        # Search by keyword
        resp = admin_client.get("/admin/support?q=ATS")
        self.assertEqual(resp.status_code, 200)

    def test_05_admin_can_respond_and_notifies_user(self):
        """Admin response adds message, changes status, and sends in-app notification to user."""
        ticket = SupportTicket(
            user_id=self.alice_id,
            issue_type=SupportTicket.ISSUE_TECHNICAL,
            subject="Bug report on login",
            description="I experienced a 500 error when clicking settings",
            status=SupportTicket.STATUS_OPEN,
        )
        db.session.add(ticket)
        db.session.commit()

        initial_alice_notifs = Notification.query.filter_by(candidate_id=self.alice_id).count()

        admin_client = self._login_as("admin_support@example.com", "Admin@1234")
        resp = admin_client.post(
            f"/admin/support/{ticket.id}",
            data={
                "action": "reply",
                "message": "We have investigated and resolved the issue on your account. Please try again.",
                "status": "resolved",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Response sent successfully", resp.data)

        # Verify ticket in DB
        db.session.refresh(ticket)
        self.assertEqual(ticket.status, SupportTicket.STATUS_RESOLVED)
        self.assertEqual(len(ticket.messages), 1)
        self.assertTrue(ticket.messages[0].is_admin_response)

        # Verify Alice received in-app notification
        new_alice_notifs = Notification.query.filter_by(candidate_id=self.alice_id).count()
        self.assertEqual(new_alice_notifs, initial_alice_notifs + 1)
        latest_notif = Notification.query.filter_by(candidate_id=self.alice_id).order_by(Notification.created_at.desc()).first()
        self.assertIn(f"Ticket #{ticket.id}", latest_notif.title)
        self.assertIn(f"/support/{ticket.id}", latest_notif.link)

    def test_06_admin_quick_status_change(self):
        """Admin can change ticket status from Open to In Progress."""
        ticket = SupportTicket(
            user_id=self.alice_id,
            issue_type=SupportTicket.ISSUE_ACCOUNT,
            subject="Status Change Test",
            description="Testing quick status toggle",
            status=SupportTicket.STATUS_OPEN,
        )
        db.session.add(ticket)
        db.session.commit()

        admin_client = self._login_as("admin_support@example.com", "Admin@1234")
        resp = admin_client.post(
            f"/admin/support/{ticket.id}",
            data={
                "action": "status_change",
                "status": "in_progress",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Ticket status updated", resp.data)

        db.session.refresh(ticket)
        self.assertEqual(ticket.status, SupportTicket.STATUS_IN_PROGRESS)


if __name__ == "__main__":
    unittest.main()
