"""Comprehensive test suite for Zentra AI Provider-Fallback Cascade.

Tests all 10 provider matrix combinations:
1. Gemini available + Groq available -> Gemini used
2. Gemini unavailable + Groq available -> Groq used
3. Gemini available + Groq unavailable -> Gemini used
4. Gemini unavailable + Groq unavailable -> Local used
5. Gemini rate-limited (429) + Groq available -> Groq used
6. Gemini timeout + Groq available -> Groq used
7. Gemini invalid response + Groq available -> Groq used
8. Gemini unavailable + Groq invalid response -> Local used
9. Both API keys missing -> Local used
10. External providers completely unreachable -> Local used
"""

import unittest
from unittest.mock import MagicMock, patch

from app.ai.base import BaseAIProvider
from app.ai.gemini_provider import GeminiAIProvider
from app.ai.groq_provider import GroqAIProvider
from app.ai.local_provider import LocalAIProvider
from app.ai.service import AIService


class MockFailingProvider(BaseAIProvider):
    def __init__(self, name="mock_fail", failure_type="error"):
        self._name = name
        self.failure_type = failure_type

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self.failure_type != "unavailable"

    def improve_bullet(self, bullet, title="", company="", known_skills=None):
        if self.failure_type == "timeout":
            raise TimeoutError("Simulated request timeout")
        elif self.failure_type == "rate_limit":
            raise Exception("HTTP 429 Too Many Requests")
        elif self.failure_type == "invalid_response":
            return ""  # empty / invalid
        elif self.failure_type == "network":
            raise ConnectionError("Simulated network down")
        return None

    def generate_summary(self, headline, skills, experience_snippets, target_role=""):
        return None

    def retouch_bio(self, raw_bio, headline="", skills=None, target_role=""):
        return None

    def explain_match(self, resume_text, jd_text, ats_score, matched_skills, missing_skills):
        return None

    def generate_candidate_summary(self, candidate_name, headline, skills, experience_summary, job_title, match_score):
        return None

    def generate_interview_questions(self, job_title, requirements, candidate_skills, missing_skills):
        return None

    def improve_job_description(self, title, raw_description, requirements=""):
        return None


class MockWorkingProvider(BaseAIProvider):
    def __init__(self, name="mock_working"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return True

    def improve_bullet(self, bullet, title="", company="", known_skills=None):
        return f"[{self._name.upper()}] Engineered high-performance service for {bullet}."

    def generate_summary(self, headline, skills, experience_snippets, target_role=""):
        return f"[{self._name.upper()}] Executive summary for {headline}."

    def retouch_bio(self, raw_bio, headline="", skills=None, target_role=""):
        return f"[{self._name.upper()}] Polished bio based on: {raw_bio}"

    def explain_match(self, resume_text, jd_text, ats_score, matched_skills, missing_skills):
        return {"overview": f"[{self._name.upper()}] Match explanation"}

    def generate_candidate_summary(self, candidate_name, headline, skills, experience_summary, job_title, match_score):
        return {"executive_summary": f"[{self._name.upper()}] Candidate dossier"}

    def generate_interview_questions(self, job_title, requirements, candidate_skills, missing_skills):
        return [f"[{self._name.upper()}] Tell us about your technical leadership in {job_title}."]

    def improve_job_description(self, title, raw_description, requirements=""):
        return {"summary": f"[{self._name.upper()}] Improved JD for {title}"}


class TestAIProviderCascade(unittest.TestCase):

    def test_1_gemini_and_groq_available(self):
        """Scenario 1: Gemini available + Groq available -> Gemini must be used."""
        service = AIService(
            gemini_provider=MockWorkingProvider("gemini"),
            groq_provider=MockWorkingProvider("groq"),
            local_provider=LocalAIProvider(),
        )
        res, provider = service.improve_bullet("fixed database queries", "Backend Dev", "Acme")
        self.assertEqual(provider, "gemini")
        self.assertIn("[GEMINI]", res)

    def test_2_gemini_unavailable_groq_available(self):
        """Scenario 2: Gemini unavailable + Groq available -> Groq must be used."""
        service = AIService(
            gemini_provider=MockFailingProvider("gemini", failure_type="unavailable"),
            groq_provider=MockWorkingProvider("groq"),
            local_provider=LocalAIProvider(),
        )
        res, provider = service.improve_bullet("built user auth", "Fullstack", "Corp")
        self.assertEqual(provider, "groq")
        self.assertIn("[GROQ]", res)

    def test_3_gemini_available_groq_unavailable(self):
        """Scenario 3: Gemini available + Groq unavailable -> Gemini must be used."""
        service = AIService(
            gemini_provider=MockWorkingProvider("gemini"),
            groq_provider=MockFailingProvider("groq", failure_type="unavailable"),
            local_provider=LocalAIProvider(),
        )
        res, provider = service.improve_bullet("deployed microservices", "DevOps", "CloudTech")
        self.assertEqual(provider, "gemini")
        self.assertIn("[GEMINI]", res)

    def test_4_gemini_and_groq_unavailable(self):
        """Scenario 4: Gemini unavailable + Groq unavailable -> Local implementation must be used."""
        service = AIService(
            gemini_provider=MockFailingProvider("gemini", failure_type="unavailable"),
            groq_provider=MockFailingProvider("groq", failure_type="unavailable"),
            local_provider=LocalAIProvider(),
        )
        res, provider = service.improve_bullet("responsible for database design", "Data Engineer", "DataCorp")
        self.assertEqual(provider, "local")
        self.assertTrue(res.startswith("Developed database design"))

    def test_5_gemini_rate_limited_groq_available(self):
        """Scenario 5: Gemini rate limited (429) + Groq available -> Groq."""
        service = AIService(
            gemini_provider=MockFailingProvider("gemini", failure_type="rate_limit"),
            groq_provider=MockWorkingProvider("groq"),
            local_provider=LocalAIProvider(),
        )
        res, provider = service.improve_bullet("wrote unit tests", "QA Engineer", "FinTech")
        self.assertEqual(provider, "groq")
        self.assertIn("[GROQ]", res)

    def test_6_gemini_timeout_groq_available(self):
        """Scenario 6: Gemini timeout + Groq available -> Groq."""
        service = AIService(
            gemini_provider=MockFailingProvider("gemini", failure_type="timeout"),
            groq_provider=MockWorkingProvider("groq"),
            local_provider=LocalAIProvider(),
        )
        res, provider = service.improve_bullet("sped up page load times", "Frontend Engineer", "WebCo")
        self.assertEqual(provider, "groq")
        self.assertIn("[GROQ]", res)

    def test_7_gemini_invalid_response_groq_available(self):
        """Scenario 7: Gemini invalid response + Groq available -> Groq."""
        service = AIService(
            gemini_provider=MockFailingProvider("gemini", failure_type="invalid_response"),
            groq_provider=MockWorkingProvider("groq"),
            local_provider=LocalAIProvider(),
        )
        res, provider = service.improve_bullet("helped with react components", "UI Dev", "Pixel")
        self.assertEqual(provider, "groq")
        self.assertIn("[GROQ]", res)

    def test_8_gemini_unavailable_groq_invalid_response(self):
        """Scenario 8: Gemini unavailable + Groq invalid response -> Local."""
        service = AIService(
            gemini_provider=MockFailingProvider("gemini", failure_type="unavailable"),
            groq_provider=MockFailingProvider("groq", failure_type="invalid_response"),
            local_provider=LocalAIProvider(),
        )
        res, provider = service.improve_bullet("helped to deploy containers", "SRE", "CloudCorp")
        self.assertEqual(provider, "local")
        self.assertTrue(len(res) > 5)

    def test_9_both_api_keys_missing(self):
        """Scenario 9: Both API keys missing -> Local."""
        real_gemini = GeminiAIProvider(api_key="")
        real_groq = GroqAIProvider(api_key="")
        service = AIService(
            gemini_provider=real_gemini,
            groq_provider=real_groq,
            local_provider=LocalAIProvider(),
        )
        self.assertFalse(real_gemini.is_available())
        self.assertFalse(real_groq.is_available())
        res, provider = service.improve_bullet("worked on backend api", "Backend", "Tech")
        self.assertEqual(provider, "local")
        self.assertTrue(res.startswith("Developed backend api"))

    def test_10_external_providers_completely_unreachable(self):
        """Scenario 10: External providers completely unreachable (network errors) -> Local."""
        service = AIService(
            gemini_provider=MockFailingProvider("gemini", failure_type="network"),
            groq_provider=MockFailingProvider("groq", failure_type="network"),
            local_provider=LocalAIProvider(),
        )
        res, provider = service.improve_bullet("made redis cache layer", "Senior Engineer", "Scale")
        self.assertEqual(provider, "local")
        self.assertTrue(res.startswith("Engineered redis cache layer"))

    def test_11_retouch_bio_cascade(self):
        """Scenario 11: Retouch bio cascades Gemini -> Groq -> Local fallback correctly."""
        # 1. Gemini working
        s1 = AIService(gemini_provider=MockWorkingProvider("gemini"), groq_provider=MockWorkingProvider("groq"))
        res, provider = s1.retouch_bio("i like python and django", headline="Backend Dev", skills=["Python", "Django"])
        self.assertEqual(provider, "gemini")
        self.assertIn("Polished bio", res)

        # 2. Gemini fails -> Groq succeeds
        s2 = AIService(gemini_provider=MockFailingProvider("gemini", failure_type="rate_limit"), groq_provider=MockWorkingProvider("groq"))
        res, provider = s2.retouch_bio("i build mobile apps with flutter", headline="Mobile Dev", skills=["Flutter"])
        self.assertEqual(provider, "groq")
        self.assertIn("Polished bio", res)

        # 3. Both external fail -> Local fallback
        s3 = AIService(gemini_provider=MockFailingProvider("gemini"), groq_provider=MockFailingProvider("groq"))
        res, provider = s3.retouch_bio("frontend web dev react", headline="Frontend Engineer", skills=["React", "TypeScript"])
        self.assertEqual(provider, "local")
        self.assertIn("Frontend Engineer", res)
        self.assertIn("React", res)


if __name__ == "__main__":
    unittest.main()
