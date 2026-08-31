"""Google Gemini Generative AI Provider for Zentra.

Implements BaseAIProvider using Google Gemini API over lightweight HTTPS REST.
Follows zero-crash, strict-timeout, and safe error handling.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional

import requests

from app.ai.base import BaseAIProvider

logger = logging.getLogger(__name__)


class GeminiAIProvider(BaseAIProvider):
    """Google Gemini AI Provider."""

    API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    FALLBACK_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 6):
        self._api_key = api_key
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "gemini"

    def _get_key(self) -> str:
        if self._api_key is not None:
            return self._api_key.strip()
        return os.environ.get("GEMINI_API_KEY", "").strip()

    def is_available(self) -> bool:
        key = self._get_key()
        return bool(key and len(key) > 8 and not key.startswith("change-me"))

    def _call_gemini(self, prompt: str, system_instruction: str = "", temperature: float = 0.2) -> Optional[str]:
        """Executes a sanitized REST request to Gemini with strict timeout and error capture."""
        key = self._get_key()
        if not key:
            return None

        payload: Dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 1000,
            }
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        headers = {
            "Content-Type": "application/json"
        }

        urls_to_try = [
            f"{self.API_URL}?key={key}",
            f"{self.FALLBACK_URL}?key={key}",
        ]

        for url in urls_to_try:
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
                elif response.status_code in (401, 403, 429):
                    logger.warning(f"Gemini API returned HTTP {response.status_code}; failing over.")
                    return None
                else:
                    logger.warning(f"Gemini API returned HTTP {response.status_code}")
            except requests.exceptions.Timeout:
                logger.warning("Gemini API request timed out; failing over.")
                return None
            except Exception as e:
                logger.warning(f"Gemini API call failed ({type(e).__name__}); failing over.")
                return None

        return None

    def improve_bullet(
        self,
        bullet: str,
        title: str = "",
        company: str = "",
        known_skills: Optional[List[str]] = None,
    ) -> Optional[str]:
        system_prompt = (
            "You are an expert ATS Resume Coach. Rewrite the candidate's resume bullet point to make it active, "
            "results-oriented, and high-impact. Strict rules: Never invent metrics or skills not in the original text. "
            "Output ONLY the improved single bullet text without quotes, markdown list markers, or commentary."
        )
        user_prompt = f"Role: {title or 'Software Engineer'}\nCompany: {company or 'Tech'}\nOriginal Bullet: {bullet}\n\nImproved single bullet point:"

        result = self._call_gemini(user_prompt, system_instruction=system_prompt, temperature=0.3)
        if result:
            # Clean any leading bullet chars or quotes
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
        system_prompt = (
            "You are a career strategist. Write a crisp, 2-3 sentence executive professional summary for a resume. "
            "Highlight strengths and competencies without buzzword fluff. Output ONLY the summary paragraph."
        )
        skills_str = ", ".join(skills[:8]) if skills else "Modern engineering stack"
        user_prompt = (
            f"Headline: {headline}\nTarget Role: {target_role}\nCore Skills: {skills_str}\n"
            f"Key Experience: {' | '.join(experience_snippets[:3]) if experience_snippets else 'Full lifecycle delivery'}\n\n"
            "Professional Summary:"
        )

        result = self._call_gemini(user_prompt, system_instruction=system_prompt, temperature=0.3)
        return result.strip() if result else None

    def explain_match(
        self,
        resume_text: str,
        jd_text: str,
        ats_score: float,
        matched_skills: List[str],
        missing_skills: List[str],
    ) -> Optional[Dict[str, Any]]:
        system_prompt = (
            "You are a principal technical recruiter and ATS analyst. Analyze the resume against the job description. "
            "Return a valid JSON object with keys: 'overview' (2 sentence overview), 'strengths' (list of 3 bullet strings), "
            "'gap_analysis' (list of 2-3 specific missing skill notes), 'recommendation' (1 clear sentence advice). "
            "Do NOT alter the numeric ATS score. Output valid JSON only."
        )
        user_prompt = (
            f"ATS Score: {ats_score}%\n"
            f"Matched Skills: {', '.join(matched_skills[:8])}\n"
            f"Missing Skills: {', '.join(missing_skills[:6])}\n"
            f"Job Description (Snippet): {jd_text[:1200]}\n"
            f"Resume Text (Snippet): {resume_text[:1200]}\n"
        )

        raw = self._call_gemini(user_prompt, system_instruction=system_prompt, temperature=0.2)
        if raw:
            try:
                # Strip markdown json codeblock if present
                clean_json = raw.strip()
                if clean_json.startswith("```"):
                    clean_json = clean_json.strip("`")
                    if clean_json.startswith("json"):
                        clean_json = clean_json[4:].strip()
                parsed = json.loads(clean_json)
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
        system_prompt = (
            "You are an executive talent recruiter. Provide a quick candidate evaluation dossier for hiring managers. "
            "Return valid JSON with keys: 'executive_summary' (2 sentences), 'key_strengths' (list of 3 strings), 'hiring_verdict' (1 sentence)."
        )
        user_prompt = (
            f"Candidate: {candidate_name} ({headline})\n"
            f"Role Applied: {job_title}\n"
            f"ATS Match: {match_score}%\n"
            f"Skills: {', '.join(skills[:8])}\n"
            f"Experience highlights: {experience_summary[:800]}\n"
        )
        raw = self._call_gemini(user_prompt, system_instruction=system_prompt, temperature=0.2)
        if raw:
            try:
                clean_json = raw.strip()
                if clean_json.startswith("```"):
                    clean_json = clean_json.strip("`")
                    if clean_json.startswith("json"):
                        clean_json = clean_json[4:].strip()
                parsed = json.loads(clean_json)
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
        system_prompt = (
            "You are a senior hiring manager. Generate 4 tailored, high-signal technical and scenario-based interview questions "
            "specifically targeting this candidate's stated skills and any potential experience gaps for the role. "
            "Return valid JSON as an array of question strings."
        )
        user_prompt = (
            f"Role: {job_title}\n"
            f"Job Requirements: {requirements[:800]}\n"
            f"Candidate Skills: {', '.join(candidate_skills[:8])}\n"
            f"Identified Gaps: {', '.join(missing_skills[:4])}\n"
        )
        raw = self._call_gemini(user_prompt, system_instruction=system_prompt, temperature=0.3)
        if raw:
            try:
                clean_json = raw.strip()
                if clean_json.startswith("```"):
                    clean_json = clean_json.strip("`")
                    if clean_json.startswith("json"):
                        clean_json = clean_json[4:].strip()
                parsed = json.loads(clean_json)
                if isinstance(parsed, list) and len(parsed) > 0:
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
        system_prompt = (
            "You are a recruitment marketing expert. Polish and structure the job posting. "
            "Return valid JSON with keys: 'summary' (clear company/role intro), 'responsibilities' (bullet points), 'requirements' (bullet points)."
        )
        user_prompt = f"Job Title: {title}\nDescription: {raw_description}\nRequirements: {requirements}\n"
        raw = self._call_gemini(user_prompt, system_instruction=system_prompt, temperature=0.3)
        if raw:
            try:
                clean_json = raw.strip()
                if clean_json.startswith("```"):
                    clean_json = clean_json.strip("`")
                    if clean_json.startswith("json"):
                        clean_json = clean_json[4:].strip()
                parsed = json.loads(clean_json)
                if isinstance(parsed, dict) and "summary" in parsed:
                    return parsed
            except Exception:
                pass
        return None
