"""Structured information extraction for Job Descriptions and Resumes.

Extracts structured information:
├── technical_skills
├── frameworks
├── languages
├── databases
├── tools
├── soft_skills
├── responsibilities
├── experience
├── education
└── certifications
"""

import re
from typing import Dict, List, Set, Tuple, Any, Optional

from app.ml.taxonomy import (
    LANGUAGES,
    FRAMEWORKS,
    DATABASES,
    TOOLS,
    TECHNICAL_SKILLS,
    SOFT_SKILLS,
    CERTIFICATIONS,
    STRUCTURED_CATEGORIES,
    SKILL_ALIASES,
    NOISE_WORDS,
)

# Compile sorted alias list (longest phrases first to prioritize multi-word matches)
_SORTED_ALIASES = sorted(SKILL_ALIASES.keys(), key=lambda x: len(x), reverse=True)

# Regex patterns for experience extraction
_EXP_YEARS_RE = re.compile(
    r"(?:(?:at\s+least|minimum|up\s+to|\+)?\s*(\d+(?:\.\d+)?)\s*(?:-\s*(\d+))?\s*(?:\+)?\s*(?:years?|yrs?))",
    re.IGNORECASE,
)

# Regex patterns for education extraction
_DEGREE_PATTERNS = [
    ("PhD", re.compile(r"\b(ph\.?d|doctorate)\b", re.IGNORECASE)),
    ("Master", re.compile(r"\b(m\.?tech|m\.?s|m\.?sc|mca|mba|pgdm|master(?:'s)?)\b", re.IGNORECASE)),
    ("Bachelor", re.compile(r"\b(b\.?tech|b\.?e|b\.?sc|bca|bba|b\.?com|b\.?a|bachelor(?:'s)?)\b", re.IGNORECASE)),
    ("Diploma", re.compile(r"\b(diploma)\b", re.IGNORECASE)),
]

_FIELD_PATTERNS = [
    "Computer Science", "Software Engineering", "Information Technology",
    "Data Science", "Statistics", "Mechanical Engineering", "Civil Engineering",
    "Electrical Engineering", "Business Analytics", "Human Resources",
    "Psychology", "Mass Communication", "Digital Marketing", "Physics", "Mathematics",
]

# Section headers for segmenting JD into Required vs Bonus
_REQUIRED_SECTION_HEADERS = [
    "requirements", "required", "must have", "qualifications", "what you need",
    "what you'll need", "minimum qualifications", "key requirements", "essential",
]

_BONUS_SECTION_HEADERS = [
    "nice to have", "bonus", "preferred", "preferred qualifications",
    "good to have", "plus", "bonus points", "what would be nice",
]

# Punctuation characters for delimiter boundary matching
_BOUNDARY_CHARS = r" \t\n\r.,;:!?()[]{}\"'\\/|<>&"

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s-]?)?\(?\d{2,5}\)?[\s-]?\d{3,5}[\s-]?\d{3,5}")


def clean_text(text: str) -> str:
    """Normalize whitespace, bullets, and unicode characters in text."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Replace unicode bullets/dashes with standard characters
    text = re.sub(r"[\u2022\u2023\u25E6\u2043\u2219\u00B7\u25AA\u25CF]", "\n• ", text)
    text = re.sub(r"[\u2013\u2014]", "-", text)
    text = re.sub(r"[\u2018\u2019]", "'", text)
    text = re.sub(r"[\u201C\u201D]", '"', text)
    # Collapse excessive spaces while preserving line breaks
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def extract_skills(text: str) -> List[str]:
    """Extract canonical skill names from text, handling multi-word phrases,
    aliases, and strictly filtering out noise words and generic verbs.
    """
    if not text:
        return []

    cleaned = clean_text(text)
    lower_text = cleaned.lower()

    padded = f" {lower_text} "

    found_skills: List[str] = []
    seen_canonical: Set[str] = set()
    matched_spans: List[Tuple[int, int]] = []

    for alias in _SORTED_ALIASES:
        canonical = SKILL_ALIASES[alias]
        if canonical in seen_canonical:
            continue

        if alias in NOISE_WORDS:
            continue

        has_special = any(c in alias for c in "+#./-")
        if has_special:
            pattern = r"(?:^|[" + re.escape(_BOUNDARY_CHARS) + r"])" + re.escape(alias) + r"(?=[" + re.escape(_BOUNDARY_CHARS) + r"]|$)"
        else:
            pattern = r"\b" + re.escape(alias) + r"\b"

        for match in re.finditer(pattern, padded):
            start, end = match.span()
            if padded[start] in _BOUNDARY_CHARS:
                start += 1
            if end > start and padded[end - 1] in _BOUNDARY_CHARS:
                end -= 1

            overlap = any(s <= start < e or s < end <= e for s, e in matched_spans)
            if not overlap:
                matched_spans.append((start, end))
                seen_canonical.add(canonical)
                found_skills.append(canonical)
                break

    return found_skills


def extract_responsibilities(text: str) -> List[str]:
    """Extract action-oriented responsibilities or work clauses."""
    cleaned = clean_text(text)
    lines = cleaned.split("\n")
    responsibilities = []
    for line in lines:
        stripped = line.strip(" •-*#\t")
        if len(stripped.split()) >= 4 and not stripped.lower().startswith(("requirements", "skills:", "education:", "summary:")):
            responsibilities.append(stripped)
    return responsibilities


def extract_certifications(text: str) -> List[str]:
    """Extract recognized industry certifications."""
    cleaned = clean_text(text)
    found_certs = []
    for cert in CERTIFICATIONS:
        pattern = r"\b" + re.escape(cert) + r"\b"
        if re.search(pattern, cleaned, re.IGNORECASE):
            found_certs.append(cert)
    return found_certs


def segment_jd_sections(jd_text: str) -> Dict[str, str]:
    """Split a job description into structured sections:
    required, bonus, responsibilities, overview.
    """
    cleaned = clean_text(jd_text)

    section_split_re = re.compile(
        r"(?<=[.;\n])\s*(?=(?:requirements|required|must have|qualifications|nice to have|bonus|preferred|good to have|responsibilities|what you'll do|what you will do):)",
        re.IGNORECASE,
    )
    normalized_jd = section_split_re.sub("\n", cleaned)
    lines = normalized_jd.split("\n")

    sections: Dict[str, List[str]] = {
        "overview": [],
        "required": [],
        "bonus": [],
        "responsibilities": [],
    }

    current_section = "overview"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lower_line = stripped.lower()

        is_header = False
        for h in _BONUS_SECTION_HEADERS:
            if lower_line.startswith(h) or (":" in lower_line and lower_line.split(":")[0].strip() == h):
                current_section = "bonus"
                is_header = True
                break

        if not is_header:
            for h in _REQUIRED_SECTION_HEADERS:
                if lower_line.startswith(h) or (":" in lower_line and lower_line.split(":")[0].strip() == h):
                    current_section = "required"
                    is_header = True
                    break

        if not is_header:
            if lower_line.startswith("responsibilities") or "what you'll do" in lower_line or "what you will do" in lower_line:
                current_section = "responsibilities"
                is_header = True

        sections[current_section].append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items()}


def extract_experience_requirements(text: str) -> Dict[str, Any]:
    """Extract required years of experience and seniority level."""
    cleaned = clean_text(text)
    matches = _EXP_YEARS_RE.findall(cleaned)

    min_years: Optional[float] = None
    max_years: Optional[float] = None

    for m in matches:
        low = float(m[0]) if m[0] else None
        high = float(m[1]) if len(m) > 1 and m[1] else None
        if low is not None:
            if min_years is None or low > min_years:
                min_years = low
            if high is not None and (max_years is None or high > max_years):
                max_years = high

    lower_text = cleaned.lower()
    seniority = "mid"
    if any(w in lower_text for w in ["senior", "sr.", "sr ", "lead", "principal", "staff"]):
        seniority = "senior"
    elif any(w in lower_text for w in ["junior", "jr.", "jr ", "entry level", "entry-level", "intern", "internship", "0-1 year", "0-2 year", "0 years", "1 years"]):
        seniority = "junior"

    return {
        "min_years": min_years,
        "max_years": max_years,
        "seniority": seniority,
    }


def extract_education(text: str) -> Dict[str, Any]:
    """Extract degrees and relevant fields of study."""
    cleaned = clean_text(text)
    detected_degrees = []
    for degree_name, pattern in _DEGREE_PATTERNS:
        if pattern.search(cleaned):
            detected_degrees.append(degree_name)

    detected_fields = []
    lower_text = cleaned.lower()
    for field in _FIELD_PATTERNS:
        if field.lower() in lower_text:
            detected_fields.append(field)

    return {
        "degrees": detected_degrees,
        "fields": detected_fields,
        "has_education": bool(detected_degrees or "education" in lower_text),
    }


def extract_structured_jd(jd_text: str) -> Dict[str, Any]:
    """Complete extraction pipeline for Job Descriptions, outputting structured concepts."""
    cleaned = clean_text(jd_text)
    sections = segment_jd_sections(cleaned)

    all_skills = extract_skills(cleaned)
    bonus_text = sections.get("bonus", "")
    bonus_skills = extract_skills(bonus_text) if bonus_text else []
    bonus_set = set(bonus_skills)

    required_skills = [s for s in all_skills if s not in bonus_set]
    if not required_skills and all_skills:
        required_skills = all_skills
        bonus_skills = []

    extracted_languages = [s for s in all_skills if s in LANGUAGES]
    extracted_frameworks = [s for s in all_skills if s in FRAMEWORKS]
    extracted_databases = [s for s in all_skills if s in DATABASES]
    extracted_tools = [s for s in all_skills if s in TOOLS]
    extracted_tech_skills = [s for s in all_skills if s in TECHNICAL_SKILLS]
    extracted_soft_skills = [s for s in all_skills if s in SOFT_SKILLS]

    responsibilities = extract_responsibilities(sections.get("responsibilities", "") or cleaned)
    exp_req = extract_experience_requirements(cleaned)
    edu_req = extract_education(cleaned)
    certifications = extract_certifications(cleaned)

    return {
        "technical_skills": extracted_tech_skills,
        "frameworks": extracted_frameworks,
        "languages": extracted_languages,
        "databases": extracted_databases,
        "tools": extracted_tools,
        "soft_skills": extracted_soft_skills,
        "responsibilities": responsibilities,
        "experience": exp_req,
        "education": edu_req,
        "certifications": certifications,
        "all_skills": all_skills,
        "required_skills": required_skills,
        "bonus_skills": bonus_skills,
        "sections": sections,
        "raw_cleaned": cleaned,
    }


def extract_structured_resume(resume_text: str) -> Dict[str, Any]:
    """Complete extraction pipeline for Resumes, outputting structured concepts."""
    cleaned = clean_text(resume_text)
    all_skills = extract_skills(cleaned)

    extracted_languages = [s for s in all_skills if s in LANGUAGES]
    extracted_frameworks = [s for s in all_skills if s in FRAMEWORKS]
    extracted_databases = [s for s in all_skills if s in DATABASES]
    extracted_tools = [s for s in all_skills if s in TOOLS]
    extracted_tech_skills = [s for s in all_skills if s in TECHNICAL_SKILLS]
    extracted_soft_skills = [s for s in all_skills if s in SOFT_SKILLS]

    responsibilities = extract_responsibilities(cleaned)
    exp_info = extract_experience_requirements(cleaned)
    edu_info = extract_education(cleaned)
    certifications = extract_certifications(cleaned)

    # Extract email and phone
    email_match = _EMAIL_RE.search(cleaned)
    phone_match = _PHONE_RE.search(cleaned)

    return {
        "technical_skills": extracted_tech_skills,
        "frameworks": extracted_frameworks,
        "languages": extracted_languages,
        "databases": extracted_databases,
        "tools": extracted_tools,
        "soft_skills": extracted_soft_skills,
        "responsibilities": responsibilities,
        "experience": exp_info,
        "education": edu_info,
        "certifications": certifications,
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0) if phone_match else None,
        "skills": all_skills,
        "skills_set": set(all_skills),
        "raw_cleaned": cleaned,
    }


def analyze_ats_compatibility(resume_text: str, structured_resume: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Audit the physical resume for ATS machine readability and structure."""
    if structured_resume is None:
        structured_resume = extract_structured_resume(resume_text)

    cleaned = clean_text(resume_text)
    lower_text = cleaned.lower()

    passed = []
    warnings = []
    score = 100

    # 1. Machine readability
    if len(cleaned) >= 200:
        passed.append("Machine-readable text extracted successfully")
    else:
        warnings.append("Resume text is very short or partially unreadable by ATS parsers")
        score -= 25

    # 2. Contact info detection
    has_contact = bool(structured_resume.get("email") or structured_resume.get("phone") or "email" in lower_text or "phone" in lower_text)
    if has_contact:
        passed.append("Contact information (email / phone) detected")
    else:
        warnings.append("No explicit contact information detected in header")
        score -= 15

    # 3. Standard Section Headings
    detected_sections = []
    if "experience" in lower_text or "work history" in lower_text or "employment" in lower_text:
        detected_sections.append("Experience")
    if "education" in lower_text or "academics" in lower_text:
        detected_sections.append("Education")
    if "skills" in lower_text or "technologies" in lower_text or "technical stack" in lower_text:
        detected_sections.append("Skills")
    if "summary" in lower_text or "profile" in lower_text or "objective" in lower_text:
        detected_sections.append("Summary")
    if "projects" in lower_text or "portfolio" in lower_text:
        detected_sections.append("Projects")

    if len(detected_sections) >= 3:
        passed.append(f"Standard section headings detected ({', '.join(detected_sections)})")
    else:
        warnings.append("Missing standard section headers (Experience, Education, Skills)")
        score -= 20

    # 4. Skills detection
    if len(structured_resume.get("skills", [])) >= 3:
        passed.append(f"{len(structured_resume['skills'])} canonical skills parsed and indexed")
    else:
        warnings.append("Few or no technical skills were distinctly recognized")
        score -= 15

    # 5. Format & Layout Checks
    lines = cleaned.split("\n")
    avg_line_len = sum(len(l) for l in lines) / max(1, len(lines))
    if "|" in cleaned and cleaned.count("|") > 15:
        warnings.append("Multiple vertical table separators detected (may affect single-column flow)")
        score -= 10
    else:
        passed.append("Clean single-column text flow without complex tables")

    if len(cleaned) < 400:
        warnings.append("Resume word count is low; recommend expanding detail on roles and impact")
        score -= 10

    score = max(20, min(100, score))

    return {
        "score": score,
        "passed": passed,
        "warnings": warnings,
    }


def analyze_resume_sections(resume_text: str, structured_resume: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Analyze each individual section of the resume (Summary, Experience, Skills, Education, Projects, Formatting)."""
    cleaned = clean_text(resume_text)
    lower_text = cleaned.lower()

    # Summary
    has_summary = "summary" in lower_text or "profile" in lower_text or "objective" in lower_text
    if has_summary and len(cleaned) > 500:
        sum_score = 92
        sum_status = "Strong"
        sum_feedback = "Clear professional summary with strong domain orientation."
    elif has_summary:
        sum_score = 75
        sum_status = "Good"
        sum_feedback = "Summary section is present. Consider adding quantifiable career highlights."
    else:
        sum_score = 45
        sum_status = "Needs Work"
        sum_feedback = "Add a 2-3 sentence professional summary highlighting your core expertise and target role."

    # Experience
    has_exp = "experience" in lower_text or "work history" in lower_text
    exp_clauses = structured_resume.get("responsibilities", [])
    has_metrics = bool(re.search(r"\d+%", cleaned) or re.search(r"\$\d+|\d+\+?\s*(?:users|clients|projects|ms)", cleaned))

    if has_exp and len(exp_clauses) >= 4 and has_metrics:
        exp_score = 95
        exp_status = "Strong"
        exp_feedback = "Comprehensive experience section with action verbs and quantifiable results."
    elif has_exp and len(exp_clauses) >= 2:
        exp_score = 82
        exp_status = "Good"
        exp_feedback = "Good role descriptions. Add more measurable metrics (e.g. % performance increase, scale)."
    else:
        exp_score = 50
        exp_status = "Needs Work"
        exp_feedback = "Expand your experience section with bullet points starting with strong action verbs."

    # Skills
    skills_count = len(structured_resume.get("skills", []))
    if skills_count >= 8:
        sk_score = 96
        sk_status = "Strong"
        sk_feedback = f"Rich technical skill inventory ({skills_count} verified skills detected)."
    elif skills_count >= 4:
        sk_score = 80
        sk_status = "Good"
        sk_feedback = f"{skills_count} skills detected. Group them into Languages, Frameworks, and Tools."
    else:
        sk_score = 48
        sk_status = "Needs Work"
        sk_feedback = "Include a dedicated Skills section listing programming languages, tools, and databases."

    # Education
    edu_info = structured_resume.get("education", {})
    if edu_info.get("degrees"):
        edu_score = 100
        edu_status = "Strong"
        edu_feedback = f"Verified degree ({', '.join(edu_info['degrees'])}) clearly identified."
    elif edu_info.get("has_education"):
        edu_score = 80
        edu_status = "Good"
        edu_feedback = "Education section detected. Ensure degree name and graduation year are explicit."
    else:
        edu_score = 40
        edu_status = "Needs Work"
        edu_feedback = "Add an Education section specifying your degree, institution, and graduation year."

    # Projects
    has_projects = "project" in lower_text or "portfolio" in lower_text or "github" in lower_text
    if has_projects and skills_count >= 5:
        proj_score = 88
        proj_status = "Strong"
        proj_feedback = "Projects and practical work demonstrate hands-on application of skills."
    elif has_projects:
        proj_score = 72
        proj_status = "Good"
        proj_feedback = "Projects mentioned. Highlight the technologies used and business/technical outcomes."
    else:
        proj_score = 55
        proj_status = "Needs Work"
        proj_feedback = "Add a Projects section with links/descriptions of representative technical projects."

    # Formatting
    compat = analyze_ats_compatibility(resume_text, structured_resume)
    fmt_score = compat["score"]
    fmt_status = "Strong" if fmt_score >= 85 else ("Good" if fmt_score >= 70 else "Needs Work")
    fmt_feedback = "ATS-compliant structure and typography." if fmt_score >= 85 else "Review formatting warnings in the ATS Compatibility tab."

    return {
        "Summary": {"score": sum_score, "status": sum_status, "feedback": sum_feedback},
        "Experience": {"score": exp_score, "status": exp_status, "feedback": exp_feedback},
        "Skills": {"score": sk_score, "status": sk_status, "feedback": sk_feedback},
        "Education": {"score": edu_score, "status": edu_status, "feedback": edu_feedback},
        "Projects": {"score": proj_score, "status": proj_status, "feedback": proj_feedback},
        "Formatting": {"score": fmt_score, "status": fmt_status, "feedback": fmt_feedback},
    }
