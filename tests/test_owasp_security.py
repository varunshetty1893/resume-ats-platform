import pytest
from app import create_app, db
from app.models.user import User
from app.models.job import Job
from app.models.recruiter_profile import RecruiterProfile


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_candidate(app):
    with app.app_context():
        user = User(
            full_name="Security Test Candidate",
            email="candidate_sec@example.com",
            role=User.ROLE_CANDIDATE,
        )
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()
        return user.id


class TestOWASPSecurityRemediation:
    def test_security_headers_present_on_all_responses(self, client):
        """Verify standard security headers: CSP, X-Frame-Options, X-Content-Type-Options, etc."""
        resp = client.get("/")
        assert resp.status_code == 200

        # Anti-Clickjacking
        assert resp.headers.get("X-Frame-Options") == "DENY"

        # Anti-MIME-Sniffing
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

        # Referrer Policy & Permissions Policy
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "camera=()" in resp.headers.get("Permissions-Policy", "")

        # Strict-Transport-Security
        assert "max-age=63072000" in resp.headers.get("Strict-Transport-Security", "")

        # Content-Security-Policy
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "https://cdn.jsdelivr.net" in csp
        assert "https://fonts.googleapis.com" in csp

    def test_cache_control_on_sensitive_and_auth_routes(self, client):
        """Verify sensitive routes return strict no-store, no-cache directives."""
        # Unauthenticated access to candidate page (triggers redirect with session / auth view)
        resp = client.get("/candidate/resume-ai")
        cache_control = resp.headers.get("Cache-Control", "")
        assert "no-store" in cache_control
        assert "no-cache" in cache_control
        assert resp.headers.get("Pragma") == "no-cache"
        assert resp.headers.get("Expires") == "0"

        # Auth login page
        resp_login = client.get("/auth/login")
        login_cache = resp_login.headers.get("Cache-Control", "")
        assert "no-store" in login_cache
        assert "no-cache" in login_cache

    def test_sql_injection_resilience_on_login(self, client):
        """Verify SQL injection payloads in login email/password do not cause SQL syntax errors or auth bypass."""
        sql_payloads = [
            "ZAP OR 1=1 -- ",
            "admin' OR '1'='1",
            "' OR 1=1 --",
            "test@example.com' UNION SELECT * FROM users --",
            "'; DROP TABLE users; --",
        ]
        for payload in sql_payloads:
            resp = client.post(
                "/auth/login",
                data={
                    "login-email": payload,
                    "login-password": "RandomPassword123!",
                    "login-submit": "Sign in",
                },
                follow_redirects=True,
            )
            # Response should safely render login page or bad request without 500 internal server error
            assert resp.status_code in (200, 400)
            assert b"Internal Server Error" not in resp.data

    def test_jobs_filter_validation_rejects_non_numeric_salary(self, client):
        """Verify non-numeric salary_min/salary_max are sanitized and ignored."""
        # Payload matching ZAP scan
        resp = client.get("/jobs?salary_min=ZAP&salary_max=jobs&experience=entry&work_mode=remote&job_type=full_time")
        assert resp.status_code == 200

        html = resp.data.decode("utf-8")
        # Ensure invalid strings 'ZAP' or 'jobs' are not reflected in salary input values
        assert 'name="salary_min" value="ZAP"' not in html
        assert 'name="salary_max" value="jobs"' not in html

    def test_subresource_integrity_and_local_tailwind_in_base_template(self, client):
        """Verify Tailwind is loaded locally from static and external CSS has SRI hashes."""
        resp = client.get("/")
        html = resp.data.decode("utf-8")

        # Tailwind must be local same-origin asset
        assert '/static/js/tailwind.min.js' in html

        # Bootstrap icons must have integrity hash and crossorigin
        assert 'integrity="sha384-XGjxtQfXaH2tnPFa9x+ruJTuLE3Aa6LhHSWRr1XeTyhezb4abCG4ccI5AkVDxqC+"' in html
        assert 'crossorigin="anonymous"' in html
