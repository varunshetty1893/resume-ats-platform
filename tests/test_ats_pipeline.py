import unittest

from app.ml.extractor import extract_structured_jd, extract_structured_resume, extract_skills
from app.ml.ats_scorer import score_resume
from app.ml.taxonomy import get_skill_relationship_strength, NOISE_WORDS


class TestATSPipeline(unittest.TestCase):

    def setUp(self):
        # 1. Backend / Nexova JD
        self.nexova_jd = (
            "Nexova is looking for a Backend Engineer to build and maintain REST APIs powering "
            "our core product. You'll work with Flask and PostgreSQL in a small, fast-moving team. "
            "Responsibilities include building scalable services, database schema design, "
            "query optimization, writing unit tests, and participating in code reviews. "
            "Required: Python, Flask, PostgreSQL, REST APIs, SQLAlchemy. "
            "Nice to have: Docker, AWS, CI/CD."
        )

        # 2. Frontend Engineer JD
        self.frontend_jd = (
            "Vortex Media is hiring a Senior Frontend Engineer. You will build high-performance "
            "web applications with React, Next.js, and TypeScript. "
            "Requirements: React, Next.js, TypeScript, Tailwind CSS, Redux, Responsive Design. "
            "Preferred: GraphQL, Jest, WebSockets. 5+ years experience required. Bachelor's in CS."
        )

        # 3. Data Scientist JD
        self.ds_jd = (
            "QuantAI is seeking a Data Scientist to build predictive models and natural language "
            "processing pipelines. "
            "Required: Python, Machine Learning, Natural Language Processing, Scikit-Learn, PyTorch, Pandas, SQL. "
            "Bonus: A/B Testing, Data Visualization, Tableau. 3+ years experience. Master's preferred."
        )

        # 4. DevOps Engineer JD
        self.devops_jd = (
            "CloudScale is looking for a DevOps Engineer to manage multi-region cloud infrastructure. "
            "Required: Kubernetes, Docker, Terraform, AWS, CI/CD, Linux, Bash. "
            "Nice to have: Prometheus, Grafana, Ansible. 3+ years of experience."
        )

        # 5. HR / Recruiter JD
        self.hr_jd = (
            "PeopleFirst is looking for an HR Executive. "
            "Required: Recruitment, Onboarding, Payroll, HRMS, Communication, Conflict Resolution. "
            "Preferred: Employee Engagement, Excel. 2+ years of experience."
        )

    def test_nexova_exact_problem_skill_extraction(self):
        """Exact test requested by user for the Nexova problem statement."""
        extracted = extract_structured_jd(self.nexova_jd)
        skills = extracted["all_skills"]

        # Expected skills
        expected_skills = [
            "Python",
            "Flask",
            "PostgreSQL",
            "REST APIs",
            "SQLAlchemy",
            "Docker",
            "Unit Testing",
            "Code Review",
            "Database Schema Design",
            "SQL/Query Optimization",
        ]
        for exp in expected_skills:
            self.assertIn(exp, skills, f"Expected '{exp}' to be extracted from Nexova JD")

        # Must NOT contain any of these non-skill / noise words
        must_not_contain = [
            "Nexova", "build", "maintain", "powering", "core", "small",
            "fast-moving", "team", "looking", "engineer", "product"
        ]
        for forbidden in must_not_contain:
            self.assertNotIn(forbidden, skills, f"'{forbidden}' must NOT appear as a skill")

    def test_structured_concept_separation(self):
        """Verify extractor produces distinct structured concepts, not just generic 'skills'."""
        sample_jd = (
            "Participate in code reviews and build scalable services. "
            "Requirements: Python, Flask, PostgreSQL, Docker, Communication. AWS Certified preferred."
        )
        extracted = extract_structured_jd(sample_jd)

        # Ensure 'participate' or 'build' is never a skill
        self.assertNotIn("participate", extracted["all_skills"])
        self.assertNotIn("build", extracted["all_skills"])

        # Check structured categories
        self.assertIn("Python", extracted["languages"])
        self.assertIn("Flask", extracted["frameworks"])
        self.assertIn("PostgreSQL", extracted["databases"])
        self.assertIn("Docker", extracted["tools"])
        self.assertIn("Communication", extracted["soft_skills"])
        self.assertIn("Code Review", extracted["technical_skills"])
        self.assertIn("AWS Certified", extracted["certifications"])
        self.assertTrue(len(extracted["responsibilities"]) >= 1)

    def test_configurable_relationship_strengths(self):
        """Verify relationship strengths: Flask ↔ FastAPI = strong, Flask ↔ Django = moderate, Flask ↔ React = 0.0."""
        self.assertEqual(get_skill_relationship_strength("Flask", "FastAPI"), 0.80)
        self.assertEqual(get_skill_relationship_strength("Flask", "Django"), 0.65)
        self.assertEqual(get_skill_relationship_strength("Flask", "React"), 0.00)
        self.assertEqual(get_skill_relationship_strength("React", "Next.js"), 0.85)
        self.assertEqual(get_skill_relationship_strength("PostgreSQL", "MySQL"), 0.80)

    def test_exact_scoring_weights_and_breakdown(self):
        """Verify breakdown has all expected keys and adds up to composite score."""
        resume = (
            "Summary: Senior Backend Engineer with 4 years in Python, Flask, PostgreSQL. "
            "Skills: Python, Flask, PostgreSQL, REST APIs, SQLAlchemy, Docker, AWS, CI/CD, Unit Testing, Code Review, Database Schema Design, SQL/Query Optimization. "
            "Experience: Built scalable services and high throughput APIs. "
            "Education: B.Tech in Computer Science."
        )
        result = score_resume(resume, self.nexova_jd)

        breakdown = result["breakdown"]
        self.assertIn("Skills Match", breakdown)
        self.assertIn("Experience Relevance", breakdown)
        self.assertIn("Responsibility Match", breakdown)
        self.assertIn("Education", breakdown)
        self.assertIn("Formatting", breakdown)
        self.assertIn("Keyword Match", breakdown)

        # Composite score calculation: 40% Skills + 20% Exp + 15% Resp + 5% Edu + 10% Format + 10% Keyword
        expected_score = int(round(
            (breakdown["Skills Match"] * 0.40) +
            (breakdown["Experience Relevance"] * 0.20) +
            (breakdown["Responsibility Match"] * 0.15) +
            (breakdown["Education"] * 0.05) +
            (breakdown["Formatting"] * 0.10) +
            (breakdown["Keyword Match"] * 0.10)
        ))
        self.assertEqual(result["score"], expected_score)

    def test_alternative_related_framework_matching(self):
        # Candidate has FastAPI instead of Flask
        resume_with_fastapi = (
            "Summary: Backend developer with 3 years of experience in Python, FastAPI, PostgreSQL, and REST APIs. "
            "Skills: Python, FastAPI, PostgreSQL, REST APIs, SQLAlchemy, Docker, Git. "
            "Experience: Built high performance REST services, designed database schemas, performed query optimization and unit testing. "
            "Education: B.Tech in Computer Science."
        )
        result = score_resume(resume_with_fastapi, self.nexova_jd)

        self.assertGreaterEqual(result["score"], 70, "Related framework FastAPI should receive substantial credit")
        self.assertIn("Python", result["matched_keywords"])
        self.assertIn("PostgreSQL", result["matched_keywords"])
        self.assertIn("REST APIs", result["matched_keywords"])
        self.assertTrue(any(r["resume_skill"] == "FastAPI" for r in result["related_skills"]))

    def test_unrelated_resume_low_score(self):
        # HR resume against backend developer JD
        hr_resume = (
            "Summary: Results-driven HR Executive with 4 years in talent acquisition, recruitment, onboarding, and payroll. "
            "Skills: recruitment, onboarding, payroll, communication, employee engagement, hrms. "
            "Experience: Managed campus hiring drives and employee performance reviews. "
            "Education: MBA in Human Resources."
        )
        result = score_resume(hr_resume, self.nexova_jd)
        self.assertLess(result["score"], 40, "Unrelated resume should receive low ATS score")

    def test_frontend_skill_extraction(self):
        extracted = extract_structured_jd(self.frontend_jd)
        skills = extracted["all_skills"]
        for exp in ["React", "Next.js", "TypeScript", "Tailwind CSS", "Redux", "GraphQL", "Responsive Design"]:
            self.assertIn(exp, skills)
        self.assertNotIn("Vortex Media", skills)
        self.assertNotIn("hiring", skills)

    def test_ds_skill_extraction(self):
        extracted = extract_structured_jd(self.ds_jd)
        skills = extracted["all_skills"]
        for exp in ["Python", "Machine Learning", "Natural Language Processing", "Scikit-Learn", "PyTorch", "Pandas", "SQL", "A/B Testing", "Data Visualization", "Tableau"]:
            self.assertIn(exp, skills)
        self.assertNotIn("QuantAI", skills)
        self.assertNotIn("seeking", skills)


if __name__ == "__main__":
    unittest.main()
