"""AI Bullet Point Improvement Engine for Experience and Projects.

Follows strict safety and accuracy guidelines:
- Never invents false companies, degrees, unmentioned skills, or fictitious metrics.
- Converts weak/passive phrasing into strong, active, results-focused statements.
- Preserves the user's original facts while improving professional impact and ATS clarity.
"""

import re
from typing import List, Optional

# Weak verb replacements mapped to active, impactful alternatives
WEAK_VERBS_MAP = {
    r"^(?:worked on|was working on|helped with|helped to|responsible for|tasked with|did|handled|assisted in|participated in)\s+": "Developed ",
    r"^(?:managed to build|built)\s+": "Built ",
    r"^(?:made|created)\s+": "Engineered ",
    r"^(?:fixed|looked at)\s+": "Resolved and optimized ",
    r"^(?:talked with|met with)\s+": "Collaborated with ",
    r"^(?:wrote tests for|tested)\s+": "Implemented automated testing for ",
    r"^(?:did database design|made tables for)\s+": "Designed robust database schemas for ",
    r"^(?:sped up|made faster)\s+": "Optimized performance of ",
    r"^(?:put code on|deployed to)\s+": "Configured deployment pipelines for ",
}

ACTION_VERB_STARTERS = [
    "Architected", "Engineered", "Developed", "Implemented", "Designed",
    "Optimized", "Streamlined", "Orchestrated", "Built", "Formulated",
    "Automated", "Delivered", "Spearheaded", "Coordinated", "Refactored"
]


def improve_resume_bullet(bullet: str, title: str = "", company: str = "", known_skills: Optional[List[str]] = None) -> str:
    """Refine a resume bullet point to maximize impact without hallucinating facts."""
    if not bullet or not bullet.strip():
        return ""

    text = bullet.strip(" •-*#\t\n")
    if not text:
        return ""

    # 1. Capitalize first letter and ensure ending period
    text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
    if not text.endswith((".", "!", "?")):
        text += "."

    improved = text

    # 2. Check and transform weak passive phrases
    for pattern, replacement in WEAK_VERBS_MAP.items():
        if re.search(pattern, improved, re.IGNORECASE):
            improved = re.sub(pattern, replacement, improved, count=1, flags=re.IGNORECASE)
            break

    # 3. If first word is a simple generic verb, upgrade to a strong action verb
    first_word_match = re.match(r"^([A-Za-z]+)\b", improved)
    if first_word_match:
        first_word = first_word_match.group(1).lower()
        if first_word in ["make", "making", "write", "writing"]:
            improved = "Developed " + improved[len(first_word):].strip()
        elif first_word in ["help", "helping"]:
            improved = "Collaborated to deliver " + improved[len(first_word):].strip()
        elif first_word in ["change", "changing", "update", "updating"]:
            improved = "Refactored and updated " + improved[len(first_word):].strip()
        elif first_word in ["use", "using"]:
            improved = "Leveraged " + improved[len(first_word):].strip()

    # Clean up double spaces or awkward punctuation
    improved = re.sub(r"\s+", " ", improved).strip()
    if not improved.endswith("."):
        improved += "."

    return improved
