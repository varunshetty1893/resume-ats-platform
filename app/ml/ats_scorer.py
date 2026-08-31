"""ATS scoring engine: Hybrid matching between resume and job description.

Combines:
1. Structured skill extraction (exact canonical matching)
2. Related / alternative skill matching via weighted taxonomy relationships (configurable strengths)
3. Required vs Bonus skill weighting inside Skills Match
4. Experience & Seniority alignment
5. Responsibility & Domain semantic matching (TF-IDF n-gram vectors)
6. Education & Formatting quality checks
7. ATS Compatibility Audit (machine readability, structure, headers)
8. Resume Section Quality Analysis (Summary, Experience, Skills, Education, Projects, Formatting)
9. Transparent score breakdown & tailored recommendations
"""

import math
import re
from typing import Dict, List, Set, Any, Tuple, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.ml.extractor import (
    extract_structured_jd,
    extract_structured_resume,
    analyze_ats_compatibility,
    analyze_resume_sections,
    clean_text,
)
from app.ml.taxonomy import get_skill_relationship_strength, SKILL_RELATIONSHIPS


def _generate_requirements_match(jd_data: Dict[str, Any], resume_data: Dict[str, Any], related_matches: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Build a human-readable list of matched and missing job requirements."""
    matched = []
    missing = []

    # Experience requirement
    exp_req = jd_data.get("experience", {})
    min_years = exp_req.get("min_years")
    resume_exp = resume_data.get("experience", {})
    res_years = resume_exp.get("min_years")

    if min_years is not None:
        req_label = f"{int(min_years)}+ years experience"
        if res_years is not None and res_years >= min_years:
            matched.append(f"{req_label} ({int(res_years)} years on resume)")
        elif res_years is not None:
            missing.append(f"{req_label} (resume states {int(res_years)} years)")
        else:
            missing.append(f"{req_label} (total years not explicitly stated)")

    # Key required skills & frameworks
    resume_skills = resume_data.get("skills_set", set())
    related_dict = {r["jd_skill"]: r["resume_skill"] for r in related_matches}

    for skill in jd_data.get("required_skills", []):
        if skill in resume_skills:
            matched.append(skill)
        elif skill in related_dict:
            matched.append(f"{skill} / similar framework (has {related_dict[skill]})")
        else:
            missing.append(skill)

    # Education requirement
    edu_req = jd_data.get("education", {})
    res_edu = resume_data.get("education", {})
    if edu_req.get("degrees"):
        deg_str = " / ".join(edu_req["degrees"])
        if any(d in res_edu.get("degrees", []) for d in edu_req["degrees"]):
            matched.append(f"{deg_str} degree")
        else:
            missing.append(f"{deg_str} degree")

    return {"matched": matched, "missing": missing}


def _generate_responsibilities_match(jd_data: Dict[str, Any], resume_data: Dict[str, Any]) -> Dict[str, List[str]]:
    """Compare JD responsibilities against candidate's experience clauses."""
    jd_resps = jd_data.get("responsibilities", [])
    resume_resps = resume_data.get("responsibilities", [])

    matched = []
    partial = []
    missing = []

    if not jd_resps:
        # Generate representative responsibility items from key skills and title
        skills = jd_data.get("required_skills", [])[:4]
        jd_resps = [f"Build and maintain services with {s}" for s in skills]

    # Clean and vectorize
    if jd_resps and resume_resps:
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        try:
            resume_block = " ".join(resume_resps)
            res_vec = vectorizer.fit_transform([resume_block])

            for resp in jd_resps:
                # If resp is too long (e.g. whole section), split by sentence
                sentences = [s.strip() for s in re.split(r"[.;•\n]", resp) if len(s.strip().split()) >= 3]
                if not sentences:
                    sentences = [resp]

                for sent in sentences[:3]:
                    try:
                        sent_vec = vectorizer.transform([sent])
                        sim = cosine_similarity(sent_vec, res_vec)[0][0]
                        clean_sent = sent.strip(" •-*#\t")
                        if sim >= 0.22:
                            if clean_sent not in matched:
                                matched.append(clean_sent)
                        elif sim >= 0.10:
                            if clean_sent not in partial:
                                partial.append(clean_sent)
                        else:
                            if clean_sent not in missing:
                                missing.append(clean_sent)
                    except Exception:
                        pass
        except Exception:
            pass

    if not matched and not partial and not missing:
        for r in jd_resps[:3]:
            matched.append(r.strip(" •-*#\t"))

    return {
        "matched": matched[:6],
        "partial": partial[:4],
        "missing": missing[:4],
    }


def score_resume(resume_text: str, jd_text: str) -> Dict[str, Any]:
    """Compute a comprehensive, explainable ATS match score between a resume and JD."""
    resume_text = (resume_text or "").strip()
    jd_text = (jd_text or "").strip()

    empty_breakdown = {
        "Skills Match": 0,
        "Experience Match": 0,
        "Job Relevance": 0,
        "ATS Compatibility": 0,
        "Resume Quality": 0,
        # Backward-compatible keys:
        "Experience Relevance": 0,
        "Responsibility Match": 0,
        "Education": 0,
        "Formatting": 0,
        "Keyword Match": 0,
    }

    if not resume_text or not jd_text:
        return {
            "score": 0,
            "tier_label": "Needs Work",
            "matched_keywords": [],
            "missing_keywords": [],
            "related_skills": [],
            "skills_ui": {"matched": [], "related": [], "missing": []},
            "requirements_match": {"matched": [], "missing": []},
            "responsibilities_match": {"matched": [], "partial": [], "missing": []},
            "ats_compatibility": {"score": 0, "passed": [], "warnings": ["No resume text provided"]},
            "section_analysis": {},
            "breakdown": empty_breakdown,
            "recommendations": ["Provide both resume text and job description to generate an ATS analysis."],
        }

    # Step 1: Structured Information Extraction
    jd_data = extract_structured_jd(jd_text)
    resume_data = extract_structured_resume(resume_text)

    jd_skills = jd_data["all_skills"]
    jd_required = jd_data["required_skills"]
    jd_bonus = jd_data["bonus_skills"]

    resume_skills_set = resume_data["skills_set"]

    # Step 2: Skill Matching with Configurable Relationship Strengths
    matched_skills: List[str] = []
    missing_required: List[str] = []
    missing_bonus: List[str] = []
    related_matches: List[Dict[str, Any]] = []

    required_credit = 0.0
    for skill in jd_required:
        if skill in resume_skills_set:
            matched_skills.append(skill)
            required_credit += 1.0
        else:
            best_related = None
            best_strength = 0.0
            for cand_skill in resume_skills_set:
                strength = get_skill_relationship_strength(skill, cand_skill)
                if strength > best_strength:
                    best_strength = strength
                    best_related = cand_skill

            if best_related and best_strength > 0.0:
                required_credit += best_strength
                related_matches.append({
                    "jd_skill": skill,
                    "resume_skill": best_related,
                    "strength": best_strength,
                })
            else:
                missing_required.append(skill)

    bonus_credit = 0.0
    for skill in jd_bonus:
        if skill in resume_skills_set:
            if skill not in matched_skills:
                matched_skills.append(skill)
            bonus_credit += 1.0
        else:
            best_related = None
            best_strength = 0.0
            for cand_skill in resume_skills_set:
                strength = get_skill_relationship_strength(skill, cand_skill)
                if strength > best_strength:
                    best_strength = strength
                    best_related = cand_skill

            if best_related and best_strength > 0.0:
                bonus_credit += best_strength
                related_matches.append({
                    "jd_skill": skill,
                    "resume_skill": best_related,
                    "strength": best_strength,
                })
            else:
                missing_bonus.append(skill)

    # Step 3: Compute Unified Skills Match Score
    req_total = len(jd_required) if jd_required else len(jd_skills)
    bonus_total = len(jd_bonus)

    if req_total > 0:
        req_score = (required_credit / req_total) * 100.0
    else:
        req_score = 100.0 if not jd_skills else 50.0

    if bonus_total > 0:
        bonus_score = (bonus_credit / bonus_total) * 100.0
        skills_match_score = (req_score * 0.85) + (bonus_score * 0.15)
    else:
        skills_match_score = req_score

    skills_match_score = max(0.0, min(100.0, skills_match_score))

    # Step 4: Experience Matching (20%)
    jd_exp = jd_data["experience"]
    resume_exp = resume_data["experience"]

    jd_min_years = jd_exp.get("min_years")
    resume_min_years = resume_exp.get("min_years")

    if jd_min_years is not None:
        if resume_min_years is not None:
            if resume_min_years >= jd_min_years:
                experience_score = 100.0
            else:
                ratio = resume_min_years / jd_min_years
                experience_score = max(35.0, min(90.0, ratio * 100.0))
        else:
            clause_count = len(resume_data["responsibilities"])
            experience_score = min(85.0, 50.0 + (clause_count * 5.0))
    else:
        clause_count = len(resume_data["responsibilities"])
        experience_score = min(95.0, 70.0 + (clause_count * 3.0))

    jd_seniority = jd_exp.get("seniority", "mid")
    resume_seniority = resume_exp.get("seniority", "mid")
    if jd_seniority == resume_seniority:
        experience_score = min(100.0, experience_score + 5.0)
    elif jd_seniority == "senior" and resume_seniority == "junior":
        experience_score = max(30.0, experience_score - 20.0)

    # Step 5: Responsibility & Job Relevance (15%) & Keyword/Semantic (10%)
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    try:
        tfidf_matrix = vectorizer.fit_transform([resume_data["raw_cleaned"], jd_data["raw_cleaned"]])
        cosine_sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        if cosine_sim <= 0.05:
            resp_score = max(0.0, float(cosine_sim) * 120.0)
            keyword_score = max(0.0, float(cosine_sim) * 150.0)
        else:
            resp_score = min(100.0, 20.0 + ((float(cosine_sim) - 0.05) / 0.25) * 65.0)
            keyword_score = min(100.0, 25.0 + ((float(cosine_sim) - 0.05) / 0.25) * 70.0)
    except Exception:
        resp_score = skills_match_score
        keyword_score = skills_match_score

    job_relevance_score = int(round((resp_score * 0.60) + (keyword_score * 0.40)))

    # Step 6: Education (5%)
    jd_edu = jd_data["education"]
    resume_edu = resume_data["education"]

    if jd_edu.get("degrees"):
        jd_degs = set(jd_edu["degrees"])
        res_degs = set(resume_edu["degrees"])
        if res_degs.intersection(jd_degs):
            education_score = 100.0
        elif res_degs:
            education_score = 85.0
        elif resume_edu.get("has_education"):
            education_score = 70.0
        else:
            education_score = 45.0
    else:
        education_score = 100.0 if resume_edu.get("has_education") else 60.0

    # Step 7: ATS Compatibility & Resume Section Analysis
    ats_compatibility_data = analyze_ats_compatibility(resume_text, resume_data)
    ats_compatibility_score = ats_compatibility_data["score"]

    section_analysis = analyze_resume_sections(resume_text, resume_data)
    section_scores = [v["score"] for v in section_analysis.values()]
    resume_quality_score = int(round(sum(section_scores) / max(1, len(section_scores))))
    formatting_score = section_analysis["Formatting"]["score"]

    # Step 8: Composite Final ATS Score (40% Skills + 20% Exp + 15% Resp + 5% Edu + 10% Formatting + 10% Keyword)
    composite = (
        (skills_match_score * 0.40) +
        (experience_score * 0.20) +
        (resp_score * 0.15) +
        (education_score * 0.05) +
        (formatting_score * 0.10) +
        (keyword_score * 0.10)
    )

    final_score = int(round(max(0.0, min(100.0, composite))))

    if final_score >= 80:
        tier_label = "Strong Match"
    elif final_score >= 70:
        tier_label = "Good Match"
    elif final_score >= 50:
        tier_label = "Moderate Match"
    else:
        tier_label = "Needs Work"

    missing_all = missing_required + [b for b in missing_bonus if b not in missing_required]

    # Step 9: Structured Requirements and Responsibilities matching
    reqs_match = _generate_requirements_match(jd_data, resume_data, related_matches)
    resps_match = _generate_responsibilities_match(jd_data, resume_data)

    # Step 10: Actionable Recommendations
    recommendations: List[str] = []
    if missing_required:
        for m in missing_required[:3]:
            recommendations.append(f"Add required skill '{m}' to your Skills or Experience section.")

    if related_matches:
        rel = related_matches[0]
        strength_desc = "strong alternative" if rel.get("strength", 0.6) >= 0.8 else "related technology"
        recommendations.append(
            f"You have '{rel['resume_skill']}' (a {strength_desc} to required '{rel['jd_skill']}'). Highlight both or emphasize transferable experience."
        )

    if jd_min_years is not None and (resume_min_years is None or resume_min_years < jd_min_years):
        recommendations.append(
            f"The job asks for {int(jd_min_years)}+ years of experience. Clearly state your total experience timeline."
        )

    if "project" not in resume_text.lower() and "projects" not in resume_text.lower():
        recommendations.append("Include a Projects section with measurable business or technical outcomes.")

    if not resume_edu.get("has_education"):
        recommendations.append("Add an explicit Education section with your degree and institution.")

    if len(recommendations) < 3 and missing_bonus:
        for b in missing_bonus[:2]:
            recommendations.append(f"Consider mentioning nice-to-have skill '{b}' to boost your score.")

    return {
        "score": final_score,
        "tier_label": tier_label,
        "matched_keywords": matched_skills[:15],
        "missing_keywords": missing_all[:10],
        "related_skills": related_matches,
        "skills_ui": {
            "matched": matched_skills[:15],
            "related": related_matches,
            "missing": missing_all[:10],
        },
        "requirements_match": reqs_match,
        "responsibilities_match": resps_match,
        "ats_compatibility": ats_compatibility_data,
        "section_analysis": section_analysis,
        "breakdown": {
            "Skills Match": int(round(skills_match_score)),
            "Experience Match": int(round(experience_score)),
            "Job Relevance": job_relevance_score,
            "ATS Compatibility": ats_compatibility_score,
            "Resume Quality": resume_quality_score,
            # Backward-compatible keys for any legacy consumers:
            "Experience Relevance": int(round(experience_score)),
            "Responsibility Match": int(round(resp_score)),
            "Education": int(round(education_score)),
            "Formatting": int(round(formatting_score)),
            "Keyword Match": int(round(keyword_score)),
        },
        "recommendations": recommendations[:5],
    }
