"""Local rule-based / deterministic AI provider for Zentra.

Serves as the unbreakable final fallback in the provider cascade.
Reuses existing ATS heuristics, taxonomy, and local engines.
Always available, runs offline, zero external network dependency.
"""

import re
from typing import Dict, List, Any, Optional

from app.ai.base import BaseAIProvider
from app.ml.bullet_improver import improve_resume_bullet


class LocalAIProvider(BaseAIProvider):
    """Local deterministic fallback provider."""

    @property
    def name(self) -> str:
        return "local"

    def is_available(self) -> bool:
        return True

    def improve_bullet(
        self,
        bullet: str,
        title: str = "",
        company: str = "",
        known_skills: Optional[List[str]] = None,
    ) -> Optional[str]:
        return improve_resume_bullet(bullet, title=title, company=company, known_skills=known_skills)

    def generate_summary(
        self,
        headline: str,
        skills: List[str],
        experience_snippets: List[str],
        target_role: str = "",
    ) -> Optional[str]:
        role_label = target_role.strip() or headline.strip() or "Software Professional"
        skills_str = ", ".join(skills[:5]) if skills else "engineering methodologies"

        summary = (
            f"Results-driven {role_label} with proven expertise in {skills_str}. "
            f"Experienced in architecting scalable solutions, optimizing performance, and delivering high-quality business outcomes. "
            f"Passionate about leveraging modern technologies to drive measurable impact in collaborative teams."
        )
        return summary

    def retouch_bio(
        self,
        raw_bio: str,
        headline: str = "",
        skills: Optional[List[str]] = None,
        target_role: str = "",
    ) -> Optional[str]:
        role_label = target_role.strip() or headline.strip() or "Driven Professional"
        skills_list = [s.strip() for s in (skills or []) if s.strip() and len(s.strip()) > 1]
        skills_str = ", ".join(skills_list[:5]) if skills_list else "modern industry tools and domain methodologies"

        # Extract legitimate words from raw_bio, ignoring keyboard mash patterns
        cleaned_words = [w for w in re.findall(r"\b[A-Za-z0-9+#.-]+\b", raw_bio or "") if not re.match(r"^(.)\1{3,}$", w)]
        key_themes = " ".join(cleaned_words[:25]) if len(cleaned_words) > 3 else ""

        if key_themes:
            bio = (
                f"Passionate {role_label} with hands-on experience in {skills_str}. "
                f"Dedicated to {key_themes.lower() if not key_themes.isupper() else key_themes} while building scalable, high-performance solutions. "
                f"Seeking impactful opportunities to apply continuous learning and drive measurable team success."
            )
        else:
            bio = (
                f"Dedicated and results-oriented {role_label} specializing in {skills_str}. "
                f"Experienced in delivering reliable, high-quality projects, solving complex challenges, and collaborating effectively across modern workflows. "
                f"Eager to contribute technical acumen and continuous improvement to forward-thinking organizations."
            )
        return bio

    def explain_match(
        self,
        resume_text: str,
        jd_text: str,
        ats_score: float,
        matched_skills: List[str],
        missing_skills: List[str],
    ) -> Optional[Dict[str, Any]]:
        tier = "Strong Match" if ats_score >= 80 else ("Good Alignment" if ats_score >= 60 else "Moderate Match")
        matched_str = ", ".join(matched_skills[:4]) if matched_skills else "general profile competencies"
        missing_str = ", ".join(missing_skills[:3]) if missing_skills else "none identified"

        overview = (
            f"Candidate profile demonstrates a {tier} ({round(ats_score)}% ATS match) against this job description. "
            f"Strongest alignment is observed in core technical proficiencies including {matched_str}."
        )

        strengths = [
            f"Direct technical competency match in {skill}" for skill in matched_skills[:3]
        ] or ["Profile aligns with required role domain."]

        gap_analysis = [
            f"Target job specifies '{skill}' which is not explicitly highlighted on the resume."
            for skill in missing_skills[:3]
        ] or ["All primary required keywords appear to be covered in candidate credentials."]

        return {
            "overview": overview,
            "strengths": strengths,
            "gap_analysis": gap_analysis,
            "recommendation": f"Profile is well suited for review. Focus discussion on depth of experience with {matched_str}.",
        }

    def generate_candidate_summary(
        self,
        candidate_name: str,
        headline: str,
        skills: List[str],
        experience_summary: str,
        job_title: str,
        match_score: float,
    ) -> Optional[Dict[str, Any]]:
        top_skills = ", ".join(skills[:5]) if skills else "General technical skills"
        name = candidate_name or "The candidate"
        
        briefing = (
            f"{name} is a {headline or 'Professional'} evaluated at {round(match_score)}% compatibility for the {job_title} role. "
            f"Core proficiencies include {top_skills}."
        )
        
        return {
            "executive_summary": briefing,
            "key_strengths": [
                f"Demonstrated background in {skill}" for skill in skills[:3]
            ],
            "hiring_verdict": "Recommended for technical screening" if match_score >= 65 else "Review for transferable skills",
        }

    def generate_interview_questions(
        self,
        job_title: str,
        requirements: str,
        candidate_skills: List[str],
        missing_skills: List[str],
    ) -> Optional[List[str]]:
        questions = []
        if candidate_skills:
            primary_skill = candidate_skills[0]
            questions.append(
                f"Can you walk us through a complex project where you designed or implemented solutions using {primary_skill}?"
            )
        if len(candidate_skills) > 1:
            second_skill = candidate_skills[1]
            questions.append(
                f"How have you handled performance bottlenecks, scalability challenges, or architectural trade-offs when working with {second_skill}?"
            )
        if missing_skills:
            gap = missing_skills[0]
            questions.append(
                f"The role relies on {gap}. How would your existing technical foundations enable you to ramp up quickly in this technology?"
            )
        else:
            questions.append(
                f"How do you approach cross-functional collaboration and delivering high-reliability systems for a {job_title} position?"
            )
        questions.append(
            "Describe a situation where you had to debug a critical production incident. What was your systematic methodology?"
        )
        return questions

    def improve_job_description(
        self,
        title: str,
        raw_description: str,
        requirements: str = "",
    ) -> Optional[Dict[str, str]]:
        clean_desc = raw_description.strip()
        enhanced_summary = (
            f"We are seeking an exceptional {title} to join our engineering team. "
            f"{clean_desc if clean_desc else 'In this role, you will design, develop, and deploy scalable solutions that drive tangible business value.'}"
        )
        return {
            "summary": enhanced_summary,
            "responsibilities": (
                "• Architect, build, and maintain high-performance, scalable applications.\n"
                "• Collaborate closely with cross-functional product and design teams to deliver end-to-end features.\n"
                "• Write clean, robust, well-tested code and participate in peer architecture reviews.\n"
                "• Continuously optimize application reliability, latency, and operational efficiency."
            ),
            "requirements": requirements or (
                "• Proven background and domain experience in relevant technologies.\n"
                "• Solid understanding of software design principles, testing patterns, and API architecture.\n"
                "• Strong analytical problem-solving and communication skills."
            ),
        }
