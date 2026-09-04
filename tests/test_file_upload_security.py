"""Attachment-upload security tests for support tickets.

Phase 2 found that all three attachment-upload paths — candidate/recruiter
new-ticket submission, candidate/recruiter reply, and the admin reply
(which previously had *zero* validation of any kind) — needed real
magic-byte content verification, not just an extension allowlist. This
suite locks that in across all three, plus the underlying
inspect_file_magic() rules it depends on.
"""

import io
import unittest

from app import create_app, db
from app.models.user import User
from app.models.support_ticket import SupportTicket, SupportTicketMessage
from app.utils.file_security import inspect_file_magic, FileValidationError


REAL_PDF_HEADER = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"0" * 64
FAKE_PDF_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64  # PNG bytes named as .pdf
REAL_PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"0" * 64
REAL_OLE2_DOC_HEADER = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"0" * 64
PLAIN_TEXT_CONTENT = b"This is a plain text description of my support issue."
BINARY_DISGUISED_AS_TEXT = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xfe\x00\x01"


class TestFileSecurityValidator(unittest.TestCase):
    """Direct unit tests of inspect_file_magic(), independent of any route."""

    def test_support_attachment_accepts_real_pdf(self):
        ext = inspect_file_magic(io.BytesIO(REAL_PDF_HEADER), "resume.pdf", allowed_category="support_attachment")
        self.assertEqual(ext, "pdf")

    def test_support_attachment_rejects_content_type_spoofing(self):
        with self.assertRaises(FileValidationError):
            inspect_file_magic(io.BytesIO(FAKE_PDF_PNG_BYTES), "resume.pdf", allowed_category="support_attachment")

    def test_support_attachment_accepts_real_legacy_doc(self):
        ext = inspect_file_magic(io.BytesIO(REAL_OLE2_DOC_HEADER), "notes.doc", allowed_category="support_attachment")
        self.assertEqual(ext, "doc")

    def test_support_attachment_rejects_spoofed_doc(self):
        with self.assertRaises(FileValidationError):
            inspect_file_magic(io.BytesIO(REAL_PNG_HEADER), "notes.doc", allowed_category="support_attachment")

    def test_support_attachment_accepts_plain_text(self):
        ext = inspect_file_magic(io.BytesIO(PLAIN_TEXT_CONTENT), "notes.txt", allowed_category="support_attachment")
        self.assertEqual(ext, "txt")

    def test_support_attachment_rejects_binary_disguised_as_text(self):
        with self.assertRaises(FileValidationError):
            inspect_file_magic(io.BytesIO(BINARY_DISGUISED_AS_TEXT), "notes.txt", allowed_category="support_attachment")

    def test_resume_category_no_longer_accepts_doc_at_all(self):
        """.doc has no working text extractor (python-docx only reads OOXML/
        zip-format .docx) — resumes must reject it outright rather than
        accept-then-crash-on-parse."""
        with self.assertRaises(FileValidationError):
            inspect_file_magic(io.BytesIO(REAL_OLE2_DOC_HEADER), "resume.doc", allowed_category="resume")

    def test_resume_category_rejects_content_type_spoofing(self):
        with self.assertRaises(FileValidationError):
            inspect_file_magic(io.BytesIO(FAKE_PDF_PNG_BYTES), "resume.pdf", allowed_category="resume")

    def test_avatar_category_rejects_non_image_extension(self):
        with self.assertRaises(FileValidationError):
            inspect_file_magic(io.BytesIO(REAL_PDF_HEADER), "avatar.pdf", allowed_category="avatar")

    def test_unknown_extension_rejected_up_front(self):
        with self.assertRaises(FileValidationError):
            inspect_file_magic(io.BytesIO(b"whatever"), "malware.exe", allowed_category="support_attachment")


class TestSupportAttachmentUploadRoutes(unittest.TestCase):
    """End-to-end: the same validation enforced through the real routes,
    across all three upload surfaces (submitter, replier, admin replier)."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()

        cls.admin_user = User(
            full_name="Upload Admin", email="upload_admin@example.com",
            role=User.ROLE_ADMIN, is_active_account=True,
        )
        cls.admin_user.set_password("Admin@1234")
        cls.candidate = User(
            full_name="Upload Candidate", email="upload_candidate@example.com",
            role=User.ROLE_CANDIDATE, is_active_account=True, public_slug="upload-candidate",
        )
        cls.candidate.set_password("Candidate@1234")
        db.session.add_all([cls.admin_user, cls.candidate])
        db.session.commit()
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

    def test_new_ticket_rejects_spoofed_pdf_attachment(self):
        client = self._login("upload_candidate@example.com", "Candidate@1234")
        before = SupportTicket.query.count()
        resp = client.post(
            "/support/new",
            data={
                "subject": "Spoofed attachment test",
                "issue_type": "other",
                "description": "Testing a spoofed PDF upload.",
                "attachment": (io.BytesIO(FAKE_PDF_PNG_BYTES), "evil.pdf"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        # Rejected before a ticket is ever created for it.
        self.assertEqual(SupportTicket.query.count(), before)

    def test_new_ticket_accepts_real_pdf_attachment(self):
        client = self._login("upload_candidate@example.com", "Candidate@1234")
        before = SupportTicket.query.count()
        resp = client.post(
            "/support/new",
            data={
                "subject": "Legit attachment test",
                "issue_type": "other",
                "description": "Testing a real PDF upload.",
                "attachment": (io.BytesIO(REAL_PDF_HEADER), "screenshot.pdf"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(SupportTicket.query.count(), before + 1)
        ticket = SupportTicket.query.order_by(SupportTicket.id.desc()).first()
        self.assertIsNotNone(ticket.attachment_filename)

    def test_admin_reply_rejects_spoofed_attachment(self):
        """This is the path Phase 2 found had *zero* validation at all
        (raw request.files access, no form, no extension check) — the
        highest-severity finding in that pass."""
        ticket = SupportTicket(
            user_id=self.candidate_id, subject="Admin reply upload test",
            issue_type="other", description="For admin-reply attachment test.",
        )
        db.session.add(ticket)
        db.session.commit()
        ticket_id = ticket.id

        client = self._login("upload_admin@example.com", "Admin@1234")
        resp = client.post(
            f"/admin/support/{ticket_id}",
            data={
                "action": "reply",
                "message": "Here's a spoofed file.",
                "attachment": (io.BytesIO(FAKE_PDF_PNG_BYTES), "evil.pdf"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        messages_with_attachment = SupportTicketMessage.query.filter_by(
            ticket_id=ticket_id
        ).filter(SupportTicketMessage.attachment_filename.isnot(None)).count()
        self.assertEqual(messages_with_attachment, 0)

    def test_admin_reply_accepts_real_attachment(self):
        ticket = SupportTicket(
            user_id=self.candidate_id, subject="Admin reply legit upload test",
            issue_type="other", description="For admin-reply attachment test.",
        )
        db.session.add(ticket)
        db.session.commit()
        ticket_id = ticket.id

        client = self._login("upload_admin@example.com", "Admin@1234")
        resp = client.post(
            f"/admin/support/{ticket_id}",
            data={
                "action": "reply",
                "message": "Here's a real file.",
                "attachment": (io.BytesIO(REAL_PDF_HEADER), "response.pdf"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        messages_with_attachment = SupportTicketMessage.query.filter_by(
            ticket_id=ticket_id
        ).filter(SupportTicketMessage.attachment_filename.isnot(None)).count()
        self.assertEqual(messages_with_attachment, 1)


if __name__ == "__main__":
    unittest.main()
