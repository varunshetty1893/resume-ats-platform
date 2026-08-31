"""Base interface for all Zentra AI providers (Gemini, Groq, Local).

Every provider implements a unified schema so callers can switch transparently
across providers without altering business logic.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class BaseAIProvider(ABC):
    """Abstract base class for generative AI providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifier for the provider (e.g. 'gemini', 'groq', 'local')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider has valid configuration and is reachable."""
        pass

    @abstractmethod
    def improve_bullet(
        self,
        bullet: str,
        title: str = "",
        company: str = "",
        known_skills: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Refines a single resume bullet into an active, high-impact phrasing."""
        pass

    @abstractmethod
    def generate_summary(
        self,
        headline: str,
        skills: List[str],
        experience_snippets: List[str],
        target_role: str = "",
    ) -> Optional[str]:
        """Generates a concise 2-3 sentence professional summary tailored to target role."""
        pass

    @abstractmethod
    def explain_match(
        self,
        resume_text: str,
        jd_text: str,
        ats_score: float,
        matched_skills: List[str],
        missing_skills: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Generates an executive explanation of why a candidate matches a job."""
        pass

    @abstractmethod
    def generate_candidate_summary(
        self,
        candidate_name: str,
        headline: str,
        skills: List[str],
        experience_summary: str,
        job_title: str,
        match_score: float,
    ) -> Optional[Dict[str, Any]]:
        """Generates recruiter-facing candidate intelligence briefing & key strengths."""
        pass

    @abstractmethod
    def generate_interview_questions(
        self,
        job_title: str,
        requirements: str,
        candidate_skills: List[str],
        missing_skills: List[str],
    ) -> Optional[List[str]]:
        """Generates 3-5 tailored technical/behavioral interview questions for a recruiter."""
        pass

    @abstractmethod
    def improve_job_description(
        self,
        title: str,
        raw_description: str,
        requirements: str = "",
    ) -> Optional[Dict[str, str]]:
        """Polishes a recruiter's job description for clarity, responsibilities, and impact."""
        pass
