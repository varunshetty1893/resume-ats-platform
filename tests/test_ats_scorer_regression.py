"""Pinned scoring regression tests for app.ml.ats_scorer.

Unlike test_ats_pipeline.py (which mostly asserts internal consistency —
e.g. that the composite score is derivable from its own breakdown, or that
a score falls above/below a threshold), this file pins the *exact* score
and breakdown component values for a handful of known resume+job fixture
pairs. The scorer is fully deterministic (no randomness anywhere in its
TF-IDF/cosine-similarity/rule-based pipeline), so a future change to
scoring weights, skill-matching rules, or the taxonomy that shifts any of
these numbers will fail loudly here — instead of silently drifting and
only being noticed when a recruiter asks why a candidate's score changed
with no edits to the job or resume.

If a change to the scorer is intentional, recompute these fixtures'
values (e.g. via a throwaway `score_resume(...)` call) and update the
expected numbers here in the same commit as the scorer change, so the
diff makes the intended shift explicit and reviewable.
"""

import unittest

from app.ml.ats_scorer import score_resume, score_resume_for_job
from app.models.job import Job


NEXOVA_JD = (
    "Nexova is looking for a Backend Engineer to build and maintain REST APIs powering "
    "our core product. You'll work with Flask and PostgreSQL in a small, fast-moving team. "
    "Responsibilities include building scalable services, database schema design, "
    "query optimization, writing unit tests, and participating in code reviews. "
    "Required: Python, Flask, PostgreSQL, REST APIs, SQLAlchemy. "
    "Nice to have: Docker, AWS, CI/CD."
)

STRONG_MATCH_RESUME = (
    "Summary: Senior Backend Engineer with 5 years in Python, Flask, PostgreSQL. "
    "Skills: Python, Flask, PostgreSQL, REST APIs, SQLAlchemy, Docker, AWS, CI/CD, Unit Testing, "
    "Code Review, Database Schema Design, SQL/Query Optimization. "
    "Experience: Built scalable REST services, designed database schemas, performed query "
    "optimization, wrote unit tests, participated in code reviews. "
    "Education: B.Tech in Computer Science."
)

UNRELATED_HR_RESUME = (
    "Summary: Results-driven HR Executive with 4 years in talent acquisition, recruitment, "
    "onboarding, and payroll. "
    "Skills: recruitment, onboarding, payroll, communication, employee engagement, hrms. "
    "Experience: Managed campus hiring drives and employee performance reviews. "
    "Education: MBA in Human Resources."
)

PARTIAL_MATCH_RESUME = (
    "Summary: Backend developer with 2 years experience in Python and Django. "
    "Skills: Python, Django, MySQL, Git. "
    "Experience: Built internal tools and simple CRUD apps. "
    "Education: B.Sc in Information Technology."
)


class TestScorerRegressionFixtures(unittest.TestCase):
    """score_resume(resume_text, jd_text) — free-text JD path (NLP-extracted skills)."""

    def test_strong_match_pinned_score_and_breakdown(self):
        result = score_resume(STRONG_MATCH_RESUME, NEXOVA_JD)
        self.assertEqual(result["score"], 92)
        self.assertEqual(result["breakdown"], {
            "Skills Match": 100,
            "Experience Match": 70,
            "Job Relevance": 97,
            "ATS Compatibility": 85,
            "Resume Quality": 77,
            "Experience Relevance": 70,
            "Responsibility Match": 95,
            "Education": 100,
            "Formatting": 85,
            "Keyword Match": 100,
        })
        self.assertEqual(result["missing_keywords"], [])

    def test_unrelated_resume_pinned_score_and_breakdown(self):
        result = score_resume(UNRELATED_HR_RESUME, NEXOVA_JD)
        self.assertEqual(result["score"], 28)
        self.assertEqual(result["breakdown"], {
            "Skills Match": 0,
            "Experience Match": 75,
            "Job Relevance": 1,
            "ATS Compatibility": 75,
            "Resume Quality": 72,
            "Experience Relevance": 75,
            "Responsibility Match": 1,
            "Education": 100,
            "Formatting": 75,
            "Keyword Match": 1,
        })
        self.assertEqual(result["matched_keywords"], [])

    def test_partial_match_pinned_score_and_breakdown(self):
        result = score_resume(PARTIAL_MATCH_RESUME, NEXOVA_JD)
        self.assertEqual(result["score"], 36)
        self.assertEqual(result["breakdown"], {
            "Skills Match": 23,
            "Experience Match": 70,
            "Job Relevance": 3,
            "ATS Compatibility": 75,
            "Resume Quality": 72,
            "Experience Relevance": 70,
            "Responsibility Match": 2,
            "Education": 100,
            "Formatting": 75,
            "Keyword Match": 3,
        })
        self.assertEqual(sorted(result["matched_keywords"]), ["Python"])

    def test_scorer_is_deterministic_across_repeated_calls(self):
        """No randomness anywhere in the pipeline — same input, same output,
        every time. If this ever fails, something (e.g. an unseeded random
        component, or a dict/set iteration-order dependency) has crept into
        the scorer, and every pinned value above would be unreliable."""
        first = score_resume(STRONG_MATCH_RESUME, NEXOVA_JD)
        for _ in range(3):
            again = score_resume(STRONG_MATCH_RESUME, NEXOVA_JD)
            self.assertEqual(again["score"], first["score"])
            self.assertEqual(again["breakdown"], first["breakdown"])


class TestScorerRegressionForJob(unittest.TestCase):
    """score_resume_for_job(resume_text, job) — the canonical production entry
    point, using a Job row's structured required_skills_raw/preferred_skills_raw
    fields instead of NLP-inferred skills. This is what apply()/edit_job()/the
    resume-builder re-score hook all actually call — a regression here is a
    regression in the score every application in the app actually stores."""

    @classmethod
    def setUpClass(cls):
        # Job() only needs SQLAlchemy's mapper registry configured (all
        # model classes imported/related) — no DB row is ever inserted in
        # this file, but instantiating a mapped class outside an app
        # context with the registry unconfigured raises, so set one up the
        # same way the other test files do.
        from app import create_app, db
        cls.app = create_app("testing")
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        from app import db
        db.session.remove()
        db.drop_all()
        cls.app_context.pop()

    def _make_job(self, **overrides):
        defaults = dict(
            title="Backend Engineer",
            description=(
                "Build and maintain REST APIs powering our core product. Work with Flask and "
                "PostgreSQL in a small, fast-moving team."
            ),
            responsibilities="Build scalable services, design database schemas, write unit tests.",
            requirements="3+ years backend experience.",
            required_skills_raw="Python, Flask, PostgreSQL, REST APIs, SQLAlchemy",
            preferred_skills_raw="Docker, AWS, CI/CD",
        )
        defaults.update(overrides)
        return Job(**defaults)

    def test_strong_match_against_structured_job_fields(self):
        job = self._make_job()
        result = score_resume_for_job(STRONG_MATCH_RESUME, job)
        self.assertEqual(result["score"], 88)
        self.assertEqual(result["breakdown"]["Skills Match"], 100)
        self.assertEqual(result["missing_keywords"], [])

    def test_partial_match_against_structured_job_fields(self):
        job = self._make_job()
        result = score_resume_for_job(PARTIAL_MATCH_RESUME, job)
        self.assertEqual(result["score"], 44)
        self.assertEqual(sorted(result["matched_keywords"]), ["Python"])

    def test_required_skills_edit_changes_the_score(self):
        """Sanity-checks the premise behind the Phase 1 recompute-on-write
        hook: changing required_skills_raw on a Job must actually change
        what score_resume_for_job() returns for the same resume, since
        _rescore_applications_for_job() relies on exactly this."""
        job_before = self._make_job(required_skills_raw="Python, Flask, PostgreSQL, REST APIs, SQLAlchemy")
        job_after = self._make_job(required_skills_raw="Python, Flask, PostgreSQL, REST APIs, SQLAlchemy, Kubernetes, GraphQL")

        score_before = score_resume_for_job(PARTIAL_MATCH_RESUME, job_before)["score"]
        score_after = score_resume_for_job(PARTIAL_MATCH_RESUME, job_after)["score"]
        self.assertNotEqual(score_before, score_after)


if __name__ == "__main__":
    unittest.main()
