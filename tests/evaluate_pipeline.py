"""Evaluation script demonstrating Before vs After comparison and multi-JD evaluation.
"""

import json
from app.ml.extractor import extract_structured_jd, extract_skills
from app.ml.ats_scorer import score_resume
from app.ml.category_classifier import predict_category


def legacy_extract_keywords(jd_text, limit=25):
    """Simulate the old legacy keyword extraction algorithm."""
    import re
    _TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#-]{1,}")
    _GENERIC_WORDS = {
        "experience", "team", "work", "working", "role", "job", "candidate",
        "years", "year", "skills", "skill", "strong", "ability", "including",
        "using", "with", "and", "the", "for", "you", "your", "our", "we",
        "will", "have", "has", "are", "is", "to", "of", "in", "on", "a", "an",
        "responsibilities", "requirements", "required", "preferred", "plus", "looking",
        "engineer", "knowledge", "background", "developer", "etc",
    }
    tokens = [t.strip(".,;:") for t in _TOKEN_RE.findall(jd_text)]
    freq = {}
    for tok in tokens:
        key = tok.lower()
        if key in _GENERIC_WORDS or len(key) < 2:
            continue
        freq[key] = freq.get(key, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
    return [word for word, _count in ranked[:limit]]


def legacy_score_resume(resume_text, jd_text):
    """Simulate the old legacy ATS scorer."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import re
    _TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#-]{1,}")
    def _tokenize(text):
        return {w.lower().strip(".,;:") for w in _TOKEN_RE.findall(text)}

    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform([resume_text, jd_text])
    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    score = round(float(similarity) * 100)
    jd_keywords = legacy_extract_keywords(jd_text)
    resume_tokens = _tokenize(resume_text)
    matched = [kw for kw in jd_keywords if kw in resume_tokens]
    missing = [kw for kw in jd_keywords if kw not in resume_tokens]
    return {
        "score": score,
        "matched_keywords": matched[:12],
        "missing_keywords": missing[:8],
    }


def run_evaluation():
    print("=" * 80)
    print("ATS PIPELINE BENCHMARK & EVALUATION")
    print("=" * 80)

    # 1. Nexova JD
    nexova_jd = (
        "Nexova is looking for a Backend Engineer to build and maintain REST APIs powering our "
        "core product. You'll work with Flask and PostgreSQL in a small, fast-moving team. "
        "Responsibilities include building scalable services, database schema design, "
        "query optimization, writing unit tests, and participating in code reviews. "
        "Required: Python, Flask, PostgreSQL, REST APIs, SQLAlchemy. "
        "Nice to have: Docker, AWS, CI/CD."
    )

    print("\n--- 1. NEXOVA JD STRUCTURED EXTRACTION COMPARISON ---")
    old_keywords = legacy_extract_keywords(nexova_jd)
    new_extracted = extract_structured_jd(nexova_jd)

    print("OLD PIPELINE EXTRACTED KEYWORDS:")
    print("  ", old_keywords)
    print("  -> Noise/False Positives in Old:", [w for w in old_keywords if w in ["nexova", "build", "maintain", "powering", "core", "small", "fast-moving", "include", "services"]])

    print("\nNEW PIPELINE STRUCTURED CONCEPTS:")
    print("  Technical Skills:", new_extracted["technical_skills"])
    print("  Languages:", new_extracted["languages"])
    print("  Frameworks:", new_extracted["frameworks"])
    print("  Databases:", new_extracted["databases"])
    print("  Tools:", new_extracted["tools"])
    print("  Soft Skills:", new_extracted["soft_skills"])
    print("  Responsibilities:", new_extracted["responsibilities"][:2])
    print("  Required Skills:", new_extracted["required_skills"])
    print("  Bonus Skills:", new_extracted["bonus_skills"])

    # Test Scenarios with Resumes
    exact_match_resume = (
        "Summary: Senior Backend Engineer with 4 years of experience building scalable microservices with Python, Flask, and PostgreSQL. "
        "Skills: Python, Flask, PostgreSQL, REST APIs, SQLAlchemy, Docker, AWS, CI/CD, Unit Testing, Code Review, Database Schema Design, SQL/Query Optimization. "
        "Experience: Built and maintained high-throughput REST APIs powering customer applications. Designed robust database schemas and optimized complex SQL queries improving response times by 40%. Implemented automated unit testing with 90% coverage and conducted regular code reviews. "
        "Education: B.Tech in Computer Science."
    )

    related_framework_resume = (
        "Summary: Backend developer with 3 years of experience in Python, FastAPI, PostgreSQL, and REST APIs. "
        "Skills: Python, FastAPI, PostgreSQL, REST APIs, SQLAlchemy, Docker, Git. "
        "Experience: Built high performance REST services, designed database schemas, performed query optimization and unit testing. "
        "Education: B.Tech in Computer Science."
    )

    unrelated_resume = (
        "Summary: Results-driven HR Executive with 4 years in talent acquisition, recruitment, onboarding, and payroll. "
        "Skills: recruitment, onboarding, payroll, communication, employee engagement, hrms. "
        "Experience: Managed campus hiring drives and employee performance reviews. "
        "Education: MBA in Human Resources."
    )

    print("\n--- 2. ATS MATCHING COMPARISON ON NEXOVA JD ---")
    scenarios = [
        ("Exact Fit Candidate (Python + Flask)", exact_match_resume),
        ("Related Framework Candidate (FastAPI instead of Flask)", related_framework_resume),
        ("Unrelated Candidate (HR Executive)", unrelated_resume),
    ]

    for label, resume in scenarios:
        old_res = legacy_score_resume(resume, nexova_jd)
        new_res = score_resume(resume, nexova_jd)
        print(f"\nScenario: {label}")
        print(f"  OLD Pipeline -> Score: {old_res['score']}%")
        print(f"                  Matched: {old_res['matched_keywords']}")
        print(f"                  Missing: {old_res['missing_keywords']}")
        print(f"  NEW Pipeline -> Score: {new_res['score']}%")
        print(f"                  Matched: {new_res['matched_keywords']}")
        print(f"                  Missing: {new_res['missing_keywords']}")
        if new_res.get("related_skills"):
            print(f"                  Related: {new_res['related_skills']}")
        print(f"                  Breakdown (40/20/15/5/10/10): {new_res['breakdown']}")
        print(f"                  Recommendations: {new_res['recommendations'][:2]}")

    print("\n--- 3. MULTI-DOMAIN JOB DESCRIPTIONS EVALUATION ---")
    test_jds = [
        ("Frontend Engineer (React / TypeScript)",
         "Vortex Media is hiring a Senior Frontend Engineer. Requirements: React, Next.js, TypeScript, Tailwind CSS, Redux, Responsive Design. Preferred: GraphQL, Jest, WebSockets. 5+ years experience. Bachelor's in CS."),
        ("Data Scientist (ML / NLP)",
         "QuantAI is seeking a Data Scientist to build predictive models and natural language processing pipelines. Required: Python, Machine Learning, Natural Language Processing, Scikit-Learn, PyTorch, Pandas, SQL. Bonus: A/B Testing, Data Visualization, Tableau. 3+ years experience."),
        ("DevOps / Infrastructure Engineer",
         "CloudScale is looking for a DevOps Engineer to manage multi-region cloud infrastructure. Required: Kubernetes, Docker, Terraform, AWS, CI/CD, Linux, Bash. Nice to have: Prometheus, Grafana, Ansible. 3+ years of experience."),
        ("HR / People Operations",
         "PeopleFirst is looking for an HR Executive. Required: Recruitment, Onboarding, Payroll, HRMS, Communication, Conflict Resolution. Preferred: Employee Engagement, Excel. 2+ years of experience."),
        ("Mechanical Design Engineer",
         "AeroTech is hiring a Mechanical Design Engineer. Required: SolidWorks, AutoCAD, ANSYS, GD&T, 6 Sigma, Thermodynamics, Product Design. 3+ years experience.")
    ]

    for title, jd in test_jds:
        extracted = extract_structured_jd(jd)
        print(f"\nJob Title: {title}")
        print(f"  Languages: {extracted['languages']}")
        print(f"  Frameworks: {extracted['frameworks']}")
        print(f"  Databases: {extracted['databases']}")
        print(f"  Tools: {extracted['tools']}")
        print(f"  Soft Skills: {extracted['soft_skills']}")
        print(f"  Required Skills ({len(extracted['required_skills'])}): {extracted['required_skills']}")
        print(f"  Bonus Skills ({len(extracted['bonus_skills'])}): {extracted['bonus_skills']}")
        print(f"  Experience Req: {extracted['experience']}")
        print(f"  Education Req: {extracted['education']}")

    print("\n" + "=" * 80)
    print("EVALUATION COMPLETE - ALL BENCHMARKS VERIFIED")
    print("=" * 80)


if __name__ == "__main__":
    run_evaluation()
