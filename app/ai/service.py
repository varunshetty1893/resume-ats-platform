"""Central AI Orchestration Service for Zentra.

Implements the strict provider-fallback cascade:
    Gemini -> Groq -> Local Fallback

Coordinates AI tasks across candidate and recruiter workflows while preserving
full system resilience, zero-crash reliability, and observability.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

from app.ai.base import BaseAIProvider
from app.ai.gemini_provider import GeminiAIProvider
from app.ai.groq_provider import GroqAIProvider
from app.ai.local_provider import LocalAIProvider

logger = logging.getLogger(__name__)


class AIService:
    """Central AI Service coordinating provider cascades."""

    def __init__(
        self,
        gemini_provider: Optional[BaseAIProvider] = None,
        groq_provider: Optional[BaseAIProvider] = None,
        local_provider: Optional[BaseAIProvider] = None,
    ):
        self.gemini = gemini_provider or GeminiAIProvider()
        self.groq = groq_provider or GroqAIProvider()
        self.local = local_provider or LocalAIProvider()

    def _get_provider_chain(self) -> List[BaseAIProvider]:
        """Returns the ordered fallback cascade: Gemini -> Groq -> Local."""
        chain: List[BaseAIProvider] = []
        if self.gemini.is_available():
            chain.append(self.gemini)
        if self.groq.is_available():
            chain.append(self.groq)
        # Local provider is always included as the unbreakable final fallback
        chain.append(self.local)
        return chain

    def get_active_provider_name(self) -> str:
        """Returns the name of the highest-priority currently available provider."""
        chain = self._get_provider_chain()
        return chain[0].name if chain else "local"

    def improve_bullet(
        self,
        bullet: str,
        title: str = "",
        company: str = "",
        known_skills: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """Improves a resume bullet point. Returns (improved_bullet, provider_used)."""
        chain = self._get_provider_chain()
        for provider in chain:
            try:
                res = provider.improve_bullet(bullet, title=title, company=company, known_skills=known_skills)
                if res and res.strip():
                    logger.info(f"AI improve_bullet served by: {provider.name}")
                    return res.strip(), provider.name
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed on improve_bullet ({type(e).__name__}); cascading.")
        
        # Safe baseline
        fallback = self.local.improve_bullet(bullet, title=title, company=company, known_skills=known_skills)
        return fallback or bullet, "local"

    def generate_summary(
        self,
        headline: str,
        skills: List[str],
        experience_snippets: List[str],
        target_role: str = "",
    ) -> Tuple[str, str]:
        """Generates a professional summary. Returns (summary, provider_used)."""
        chain = self._get_provider_chain()
        for provider in chain:
            try:
                res = provider.generate_summary(headline, skills, experience_snippets, target_role=target_role)
                if res and res.strip():
                    logger.info(f"AI generate_summary served by: {provider.name}")
                    return res.strip(), provider.name
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed on generate_summary ({type(e).__name__}); cascading.")

        fallback = self.local.generate_summary(headline, skills, experience_snippets, target_role=target_role)
        return fallback or "", "local"

    def explain_match(
        self,
        resume_text: str,
        jd_text: str,
        ats_score: float,
        matched_skills: List[str],
        missing_skills: List[str],
    ) -> Tuple[Dict[str, Any], str]:
        """Explains ATS match breakdown. Returns (explanation_dict, provider_used)."""
        chain = self._get_provider_chain()
        for provider in chain:
            try:
                res = provider.explain_match(resume_text, jd_text, ats_score, matched_skills, missing_skills)
                if res and isinstance(res, dict) and "overview" in res:
                    logger.info(f"AI explain_match served by: {provider.name}")
                    return res, provider.name
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed on explain_match ({type(e).__name__}); cascading.")

        fallback = self.local.explain_match(resume_text, jd_text, ats_score, matched_skills, missing_skills)
        return fallback or {}, "local"

    def generate_candidate_summary(
        self,
        candidate_name: str,
        headline: str,
        skills: List[str],
        experience_summary: str,
        job_title: str,
        match_score: float,
    ) -> Tuple[Dict[str, Any], str]:
        """Generates candidate briefing for recruiter. Returns (briefing_dict, provider_used)."""
        chain = self._get_provider_chain()
        for provider in chain:
            try:
                res = provider.generate_candidate_summary(
                    candidate_name, headline, skills, experience_summary, job_title, match_score
                )
                if res and isinstance(res, dict) and "executive_summary" in res:
                    logger.info(f"AI generate_candidate_summary served by: {provider.name}")
                    return res, provider.name
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed on generate_candidate_summary ({type(e).__name__}); cascading.")

        fallback = self.local.generate_candidate_summary(
            candidate_name, headline, skills, experience_summary, job_title, match_score
        )
        return fallback or {}, "local"

    def generate_interview_questions(
        self,
        job_title: str,
        requirements: str,
        candidate_skills: List[str],
        missing_skills: List[str],
    ) -> Tuple[List[str], str]:
        """Generates interview questions. Returns (questions_list, provider_used)."""
        chain = self._get_provider_chain()
        for provider in chain:
            try:
                res = provider.generate_interview_questions(job_title, requirements, candidate_skills, missing_skills)
                if res and isinstance(res, list) and len(res) > 0:
                    logger.info(f"AI generate_interview_questions served by: {provider.name}")
                    return res, provider.name
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed on generate_interview_questions ({type(e).__name__}); cascading.")

        fallback = self.local.generate_interview_questions(job_title, requirements, candidate_skills, missing_skills)
        return fallback or [], "local"

    def improve_job_description(
        self,
        title: str,
        raw_description: str,
        requirements: str = "",
    ) -> Tuple[Dict[str, str], str]:
        """Improves recruiter job description. Returns (job_dict, provider_used)."""
        chain = self._get_provider_chain()
        for provider in chain:
            try:
                res = provider.improve_job_description(title, raw_description, requirements=requirements)
                if res and isinstance(res, dict) and "summary" in res:
                    logger.info(f"AI improve_job_description served by: {provider.name}")
                    return res, provider.name
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed on improve_job_description ({type(e).__name__}); cascading.")

        fallback = self.local.improve_job_description(title, raw_description, requirements=requirements)
        return fallback or {}, "local"


# Global singleton instance
ai_service = AIService()
