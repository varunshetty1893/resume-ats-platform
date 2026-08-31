"""Groq Generative AI Provider for Zentra (Llama 3.3 / Llama 3.1 ultra-fast inference).

Implements BaseAIProvider using Groq's OpenAI-compatible Chat Completion REST API.
Operates as the ultra-fast secondary provider before falling back to Local.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional

import requests

from app.ai.base import BaseAIProvider

logger = logging.getLogger(__name__)


class GroqAIProvider(BaseAIProvider):
    """Groq AI Provider."""

    API_URL = "https://api.groq.com/openai/v1/chat/completions"
    PRIMARY_MODEL = "llama-3.3-70b-versatile"
    FALLBACK_MODEL = "llama-3.1-8b-instant"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 6):
        self._api_key = api_key
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "groq"

    def _get_key(self) -> str:
        if self._api_key is not None:
            return self._api_key.strip()
        return os.environ.get("GROQ_API_KEY", "").strip()

    def is_available(self) -> bool:
        key = self._get_key()
        return bool(key and len(key) > 8 and not key.startswith("change-me"))

    def _call_groq(self, messages: List[Dict[str, str]], temperature: float = 0.2, json_mode: bool = False) -> Optional[str]:
        """Executes a sanitized REST request to Groq with strict timeout and error capture."""
        key = self._get_key()
        if not key:
            return None

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        models_to_try = [self.PRIMARY_MODEL, self.FALLBACK_MODEL]

        for model in models_to_try:
            payload: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 1000,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}

            try:
                response = requests.post(self.API_URL, json=payload, headers=headers, timeout=self.timeout)
                if response.status_code == 200:
                    data = response.json()
                    choices = data.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        if content:
                            return content.strip()
                elif response.status_code in (401, 403, 429):
                    logger.warning(f"Groq API returned HTTP {response.status_code}; failing over.")
                    return None
                else:
                    logger.warning(f"Groq API returned HTTP {response.status_code} with model {model}")
            except requests.exceptions.Timeout:
                logger.warning("Groq API request timed out; failing over.")
                return None
            except Exception as e:
                logger.warning(f"Groq API call failed ({type(e).__name__}); failing over.")
                return None

        return None

    def improve_bullet(
        self,
        bullet: str,
        title: str = "",
        company: str = "",
        known_skills: Optional[List[str]] = None,
    ) -> Optional[str]:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert ATS Resume Coach. Rewrite the candidate's resume bullet point to make it active, "
                    "results-oriented, and high-impact. Strict rules: Never invent metrics or skills not in the original text. "
                    "Output ONLY the improved single bullet text without quotes, markdown list markers, or commentary."
                ),
            },
            {
                "role": "user",
                "content": f"Role: {title or 'Software Engineer'}\nCompany: {company or 'Tech'}\nOriginal Bullet: {bullet}\n\nImproved single bullet point:",
            }
        ]
        result = self._call_groq(messages, temperature=0.3)
        if result:
            cleaned = result.strip(" •-*#\"\n\t")
            if cleaned:
                if not cleaned.endswith((".", "!", "?")):
                    cleaned += "."
                return cleaned
        return None

    def generate_summary(
        self,
        headline: str,
        skills: List[str],
        experience_snippets: List[str],
        target_role: str = "",
    ) -> Optional[str]:
        skills_str = ", ".join(skills[:8]) if skills else "Modern engineering stack"
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a career strategist. Write a crisp, 2-3 sentence executive professional summary for a resume. "
                    "Highlight strengths and competencies without buzzword fluff. Output ONLY the summary paragraph."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Headline: {headline}\nTarget Role: {target_role}\nCore Skills: {skills_str}\n"
                    f"Key Experience: {' | '.join(experience_snippets[:3]) if experience_snippets else 'Full lifecycle delivery'}\n\n"
                    "Professional Summary:"
                ),
            }
        ]
        result = self._call_groq(messages, temperature=0.3)
        return result.strip() if result else None

    def explain_match(
        self,
        resume_text: str,
        jd_text: str,
        ats_score: float,
        matched_skills: List[str],
        missing_skills: List[str],
    ) -> Optional[Dict[str, Any]]:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a principal technical recruiter and ATS analyst. Analyze the resume against the job description. "
                    "Return a JSON object with keys: 'overview' (2 sentence overview), 'strengths' (list of 3 bullet strings), "
                    "'gap_analysis' (list of 2-3 specific missing skill notes), 'recommendation' (1 clear sentence advice). "
                    "Do NOT alter the numeric ATS score."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"ATS Score: {ats_score}%\n"
                    f"Matched Skills: {', '.join(matched_skills[:8])}\n"
                    f"Missing Skills: {', '.join(missing_skills[:6])}\n"
                    f"Job Description (Snippet): {jd_text[:1200]}\n"
                    f"Resume Text (Snippet): {resume_text[:1200]}\n"
                ),
            }
        ]
        raw = self._call_groq(messages, temperature=0.2, json_mode=True)
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and "overview" in parsed:
                    return parsed
            except Exception:
                pass
        return None

    def generate_candidate_summary(
        self,
        candidate_name: str,
        headline: str,
        skills: List[str],
        experience_summary: str,
        job_title: str,
        match_score: float,
    ) -> Optional[Dict[str, Any]]:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an executive talent recruiter. Provide a quick candidate evaluation dossier for hiring managers. "
                    "Return JSON with keys: 'executive_summary' (2 sentences), 'key_strengths' (list of 3 strings), 'hiring_verdict' (1 sentence)."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Candidate: {candidate_name} ({headline})\n"
                    f"Role Applied: {job_title}\n"
                    f"ATS Match: {match_score}%\n"
                    f"Skills: {', '.join(skills[:8])}\n"
                    f"Experience highlights: {experience_summary[:800]}\n"
                ),
            }
        ]
        raw = self._call_groq(messages, temperature=0.2, json_mode=True)
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and "executive_summary" in parsed:
                    return parsed
            except Exception:
                pass
        return None

    def generate_interview_questions(
        self,
        job_title: str,
        requirements: str,
        candidate_skills: List[str],
        missing_skills: List[str],
    ) -> Optional[List[str]]:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior hiring manager. Generate 4 tailored, high-signal technical and scenario-based interview questions "
                    "specifically targeting this candidate's stated skills and any potential experience gaps for the role. "
                    "Return JSON with a key 'questions' containing an array of 4 question strings."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Role: {job_title}\n"
                    f"Job Requirements: {requirements[:800]}\n"
                    f"Candidate Skills: {', '.join(candidate_skills[:8])}\n"
                    f"Identified Gaps: {', '.join(missing_skills[:4])}\n"
                ),
            }
        ]
        raw = self._call_groq(messages, temperature=0.3, json_mode=True)
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and "questions" in parsed and isinstance(parsed["questions"], list):
                    return [str(q).strip() for q in parsed["questions"] if str(q).strip()]
                elif isinstance(parsed, list):
                    return [str(q).strip() for q in parsed if str(q).strip()]
            except Exception:
                pass
        return None

    def improve_job_description(
        self,
        title: str,
        raw_description: str,
        requirements: str = "",
    ) -> Optional[Dict[str, str]]:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a recruitment marketing expert. Polish and structure the job posting. "
                    "Return JSON with keys: 'summary' (clear company/role intro), 'responsibilities' (bullet points), 'requirements' (bullet points)."
                ),
            },
            {
                "role": "user",
                "content": f"Job Title: {title}\nDescription: {raw_description}\nRequirements: {requirements}\n",
            }
        ]
        raw = self._call_groq(messages, temperature=0.3, json_mode=True)
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and "summary" in parsed:
                    return parsed
            except Exception:
                pass
        return None
