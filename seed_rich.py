"""
Rich seed script — generates realistic demo data for Zentra:
  • 15 companies (recruiter accounts, auto-approved)
  • 100 job postings spread across companies
  • 100 candidate accounts with resumes
  • ~300 applications with varied statuses & match scores

Run with:  python seed_rich.py
Safe to re-run — skips existing records where possible.
"""

import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from app import create_app, db
from app.models.user import User
from app.models.recruiter_profile import RecruiterProfile
from app.models.job import Job
from app.models.resume import Resume
from app.models.application import Application

app = create_app()

# ─────────────────────────────────────────────
# DATA POOLS
# ─────────────────────────────────────────────

COMPANIES = [
    {"name": "TechCorp Solutions",    "industry": "technology",    "size": "201-500",  "website": "https://techcorp.example.com",    "city": "Bangalore"},
    {"name": "DataSphere Analytics",  "industry": "technology",    "size": "51-200",   "website": "https://datasphere.example.com",  "city": "Hyderabad"},
    {"name": "Nexova Systems",        "industry": "technology",    "size": "11-50",    "website": "https://nexova.example.com",      "city": "Pune"},
    {"name": "Flowbyte AI",           "industry": "technology",    "size": "1-10",     "website": "https://flowbyte.example.com",    "city": "Chennai"},
    {"name": "ClearBank Finance",     "industry": "finance",       "size": "500+",     "website": "https://clearbank.example.com",   "city": "Mumbai"},
    {"name": "Apex Capital Group",    "industry": "finance",       "size": "201-500",  "website": "https://apexcap.example.com",     "city": "Delhi"},
    {"name": "MedPlus Health",        "industry": "healthcare",    "size": "500+",     "website": "https://medplus.example.com",     "city": "Bangalore"},
    {"name": "CareBridge Hospitals",  "industry": "healthcare",    "size": "201-500",  "website": "https://carebridge.example.com",  "city": "Hyderabad"},
    {"name": "Orion Manufacturing",   "industry": "manufacturing", "size": "500+",     "website": "https://orionmfg.example.com",    "city": "Ahmedabad"},
    {"name": "Steelwave Industries",  "industry": "manufacturing", "size": "201-500",  "website": "https://steelwave.example.com",   "city": "Surat"},
    {"name": "ShopZen Retail",        "industry": "retail",        "size": "201-500",  "website": "https://shopzen.example.com",     "city": "Mumbai"},
    {"name": "QuickMart Commerce",    "industry": "retail",        "size": "51-200",   "website": "https://quickmart.example.com",   "city": "Jaipur"},
    {"name": "CloudNine Logistics",   "industry": "other",         "size": "51-200",   "website": "https://cloudnine.example.com",   "city": "Kolkata"},
    {"name": "Pinnacle Consulting",   "industry": "other",         "size": "11-50",    "website": "https://pinnacle.example.com",    "city": "Noida"},
    {"name": "BrightEdge Media",      "industry": "other",         "size": "1-10",     "website": "https://brightedge.example.com",  "city": "Gurgaon"},
]

CONTACT_NAMES = [
    "Priya Nair", "Rahul Mehta", "Aarti Sharma", "Vikram Patel", "Sunita Reddy",
    "Arjun Kapoor", "Deepa Iyer", "Sanjay Gupta", "Neha Joshi", "Rajesh Kumar",
    "Ananya Menon", "Karan Malhotra", "Divya Singh", "Amit Tiwari", "Preeti Verma",
]

JOB_TEMPLATES = [
    {
        "title": "Senior Python Developer",
        "description": "We are looking for an experienced Python developer to build scalable backend services and APIs. You will work closely with our data and infrastructure teams to deliver high-performance solutions.",
        "responsibilities": "Design and implement RESTful APIs\nOptimize database queries and data pipelines\nConduct code reviews and mentor junior developers\nCollaborate with product and design teams",
        "requirements": "5+ years Python experience\nStrong knowledge of Flask or FastAPI\nExperience with PostgreSQL and Redis\nFamiliarity with Docker and CI/CD pipelines",
        "skills": "Python, Flask, FastAPI, PostgreSQL, Redis, Docker, REST APIs",
        "job_type": "full_time", "work_mode": "remote", "experience_level": "senior",
        "salary_min": 18, "salary_max": 30,
    },
    {
        "title": "Machine Learning Engineer",
        "description": "Join our AI team to build and deploy production-grade ML models. You'll work on NLP, recommendation systems, and predictive analytics at scale.",
        "responsibilities": "Develop and train ML models\nBuild model serving infrastructure\nCollaborate with data scientists and engineers\nMonitor model performance in production",
        "requirements": "3+ years ML engineering experience\nProficiency in Python, scikit-learn, TensorFlow or PyTorch\nExperience with MLOps tools\nStrong mathematical foundation",
        "skills": "Python, TensorFlow, PyTorch, scikit-learn, MLOps, Kubernetes, SQL",
        "job_type": "full_time", "work_mode": "hybrid", "experience_level": "senior",
        "salary_min": 22, "salary_max": 40,
    },
    {
        "title": "Data Analyst",
        "description": "We need a sharp data analyst to transform raw data into actionable business insights. You will build dashboards, run cohort analyses, and support strategic decisions.",
        "responsibilities": "Build and maintain dashboards in Tableau or Power BI\nWrite complex SQL queries for analysis\nPresent findings to business stakeholders\nIdentify trends and anomalies in data",
        "requirements": "2+ years data analysis experience\nStrong SQL skills\nExperience with Tableau, Power BI or Looker\nBasic Python or R for data manipulation",
        "skills": "SQL, Tableau, Power BI, Python, Excel, Data Visualization",
        "job_type": "full_time", "work_mode": "onsite", "experience_level": "mid",
        "salary_min": 10, "salary_max": 18,
    },
    {
        "title": "Frontend Developer (React)",
        "description": "We are building the next generation of our web platform and need a talented frontend developer who loves creating beautiful, performant user experiences.",
        "responsibilities": "Build and maintain React components and pages\nCollaborate with UX designers on implementation\nOptimize frontend performance\nWrite unit and integration tests",
        "requirements": "3+ years React.js experience\nStrong HTML, CSS, JavaScript fundamentals\nExperience with TypeScript\nFamiliarity with REST and GraphQL APIs",
        "skills": "React, TypeScript, JavaScript, HTML, CSS, REST APIs, GraphQL, Jest",
        "job_type": "full_time", "work_mode": "remote", "experience_level": "mid",
        "salary_min": 12, "salary_max": 22,
    },
    {
        "title": "Full Stack Developer",
        "description": "A versatile full-stack developer to work across our entire product — from designing database schemas to shipping polished UI features.",
        "responsibilities": "Develop end-to-end features across frontend and backend\nDesign and optimize database schemas\nParticipate in architecture discussions\nWrite clean, testable code",
        "requirements": "4+ years full-stack experience\nProficiency in Node.js or Python backend\nExperience with React or Vue.js\nStrong understanding of REST and databases",
        "skills": "Node.js, React, PostgreSQL, MongoDB, Docker, JavaScript, TypeScript",
        "job_type": "full_time", "work_mode": "hybrid", "experience_level": "mid",
        "salary_min": 14, "salary_max": 24,
    },
    {
        "title": "DevOps Engineer",
        "description": "We're scaling our infrastructure rapidly and need a skilled DevOps engineer to build automated, resilient, and observable systems.",
        "responsibilities": "Design and manage CI/CD pipelines\nMaintain Kubernetes clusters and cloud infrastructure\nImplement monitoring and alerting solutions\nCollaborate with development teams on deployment",
        "requirements": "3+ years DevOps/SRE experience\nStrong Kubernetes and Docker skills\nExperience with AWS, GCP, or Azure\nInfrastructure as Code (Terraform, Ansible)",
        "skills": "Kubernetes, Docker, AWS, GCP, Terraform, CI/CD, Linux, Prometheus",
        "job_type": "full_time", "work_mode": "remote", "experience_level": "senior",
        "salary_min": 18, "salary_max": 32,
    },
    {
        "title": "Product Manager",
        "description": "We're looking for a product manager to drive our core platform roadmap, working closely with engineering, design, and business stakeholders.",
        "responsibilities": "Define product vision and roadmap\nGather and prioritize requirements from stakeholders\nWork closely with engineering on sprint planning\nAnalyze user feedback and product metrics",
        "requirements": "3+ years product management experience\nStrong analytical and communication skills\nExperience with Agile/Scrum methodologies\nAbility to write clear product specifications",
        "skills": "Product Strategy, Agile, JIRA, Analytics, Stakeholder Management, SQL",
        "job_type": "full_time", "work_mode": "hybrid", "experience_level": "mid",
        "salary_min": 16, "salary_max": 28,
    },
    {
        "title": "UX/UI Designer",
        "description": "We need a creative UX/UI designer to craft intuitive and visually stunning product experiences that delight our users.",
        "responsibilities": "Design wireframes, prototypes, and high-fidelity mockups\nConduct user research and usability tests\nBuild and maintain design systems\nCollaborate with engineering on implementation",
        "requirements": "3+ years UX/UI design experience\nProficiency in Figma\nStrong portfolio of product design work\nUnderstanding of accessibility standards",
        "skills": "Figma, UX Research, Prototyping, Design Systems, Accessibility, CSS",
        "job_type": "full_time", "work_mode": "hybrid", "experience_level": "mid",
        "salary_min": 10, "salary_max": 20,
    },
    {
        "title": "Backend Engineer (Java)",
        "description": "Join our engineering team to build high-performance backend services using Java and Spring Boot, powering millions of transactions daily.",
        "responsibilities": "Design and implement microservices\nOptimize system performance and reliability\nWrite comprehensive unit and integration tests\nParticipate in on-call rotation",
        "requirements": "4+ years Java development experience\nStrong Spring Boot and microservices knowledge\nExperience with Kafka or RabbitMQ\nProficiency in SQL and NoSQL databases",
        "skills": "Java, Spring Boot, Kafka, PostgreSQL, MongoDB, Microservices, Docker",
        "job_type": "full_time", "work_mode": "onsite", "experience_level": "senior",
        "salary_min": 20, "salary_max": 35,
    },
    {
        "title": "QA Automation Engineer",
        "description": "We need a QA automation engineer to build robust test frameworks and ensure the quality of our rapidly evolving product.",
        "responsibilities": "Design and implement automated test frameworks\nWrite end-to-end, integration, and unit tests\nIdentify and report bugs clearly\nCollaborate with developers on test-driven development",
        "requirements": "2+ years automation testing experience\nProficiency in Selenium or Playwright\nExperience with Python or Java\nUnderstanding of CI/CD pipelines",
        "skills": "Selenium, Playwright, Python, Java, Pytest, CI/CD, JIRA, Postman",
        "job_type": "full_time", "work_mode": "hybrid", "experience_level": "mid",
        "salary_min": 8, "salary_max": 16,
    },
    {
        "title": "Cloud Infrastructure Engineer",
        "description": "We're seeking a cloud infrastructure engineer to design and maintain our AWS-based infrastructure, focusing on reliability, scalability, and cost efficiency.",
        "responsibilities": "Architect and manage AWS infrastructure\nImplement security best practices\nAutomate infrastructure with Terraform\nOptimize cloud costs",
        "requirements": "3+ years cloud infrastructure experience\nAWS Solutions Architect certification preferred\nStrong Terraform and IaC skills\nExperience with VPC, ECS, RDS, S3",
        "skills": "AWS, Terraform, Docker, Kubernetes, Python, Linux, Security",
        "job_type": "full_time", "work_mode": "remote", "experience_level": "senior",
        "salary_min": 20, "salary_max": 36,
    },
    {
        "title": "Data Scientist",
        "description": "We're building our data science capabilities and need a talented data scientist to extract insights from large datasets and build predictive models.",
        "responsibilities": "Develop and validate predictive models\nConduct statistical analysis and A/B tests\nCommunicate findings to stakeholders\nCollaborate with engineering on model deployment",
        "requirements": "3+ years data science experience\nProficiency in Python, pandas, scikit-learn\nStrong statistical knowledge\nExperience with SQL and data visualization",
        "skills": "Python, R, scikit-learn, TensorFlow, SQL, Tableau, Statistics",
        "job_type": "full_time", "work_mode": "hybrid", "experience_level": "senior",
        "salary_min": 18, "salary_max": 32,
    },
    {
        "title": "iOS Developer",
        "description": "Build world-class iOS applications that reach millions of users. You'll work in a fast-paced team shipping features weekly.",
        "responsibilities": "Develop features for our iOS app\nOptimize app performance and user experience\nReview code and mentor junior iOS developers\nIntegrate with backend APIs",
        "requirements": "3+ years iOS development experience\nStrong Swift and UIKit or SwiftUI skills\nExperience with Xcode and App Store deployment\nFamiliarity with REST APIs and JSON",
        "skills": "Swift, SwiftUI, UIKit, Xcode, REST APIs, Core Data, Combine",
        "job_type": "full_time", "work_mode": "onsite", "experience_level": "mid",
        "salary_min": 14, "salary_max": 24,
    },
    {
        "title": "Android Developer",
        "description": "We're looking for an Android developer to build performant and beautiful apps used by our growing user base across India.",
        "responsibilities": "Develop and maintain Android application features\nCollaborate with backend engineers on API integration\nOptimize app performance and battery usage\nConduct code reviews",
        "requirements": "3+ years Android development\nStrong Kotlin and Jetpack Compose knowledge\nExperience with MVVM and clean architecture\nFamiliarity with Firebase and Play Store",
        "skills": "Kotlin, Java, Android SDK, Jetpack Compose, Firebase, MVVM, REST APIs",
        "job_type": "full_time", "work_mode": "hybrid", "experience_level": "mid",
        "salary_min": 12, "salary_max": 22,
    },
    {
        "title": "Business Analyst",
        "description": "We're hiring a business analyst to bridge the gap between technology and business strategy, translating complex requirements into actionable plans.",
        "responsibilities": "Gather and document business requirements\nConduct gap analysis and process mapping\nCreate detailed functional specifications\nSupport UAT and change management",
        "requirements": "2+ years business analysis experience\nStrong communication and documentation skills\nExperience with Agile delivery\nProficiency in Excel and JIRA",
        "skills": "Business Analysis, Agile, JIRA, SQL, Excel, Process Mapping, Stakeholder Management",
        "job_type": "full_time", "work_mode": "onsite", "experience_level": "mid",
        "salary_min": 8, "salary_max": 15,
    },
    {
        "title": "Cybersecurity Analyst",
        "description": "Join our security team to protect our platform and customer data from emerging threats. You'll conduct threat analysis, incident response, and security audits.",
        "responsibilities": "Monitor security events and incidents\nConduct vulnerability assessments and penetration testing\nImplement security policies and controls\nPrepare security reports for leadership",
        "requirements": "3+ years cybersecurity experience\nKnowledge of OWASP and common attack vectors\nCEH or CISSP certification preferred\nExperience with SIEM tools",
        "skills": "Cybersecurity, Penetration Testing, OWASP, SIEM, Python, Linux, Networking",
        "job_type": "full_time", "work_mode": "hybrid", "experience_level": "senior",
        "salary_min": 16, "salary_max": 28,
    },
    {
        "title": "HR Technology Intern",
        "description": "A great opportunity for fresh graduates to gain hands-on experience working with HR systems and data analytics in a dynamic environment.",
        "responsibilities": "Assist with HR data reporting and dashboards\nSupport HRIS system maintenance\nHelp analyze employee engagement data\nDocument HR processes and workflows",
        "requirements": "Final year student or recent graduate\nBasic knowledge of Excel or Google Sheets\nGood communication skills\nEagerness to learn and grow",
        "skills": "Excel, Data Entry, Communication, HR Systems, Reporting",
        "job_type": "internship", "work_mode": "onsite", "experience_level": "entry",
        "salary_min": 3, "salary_max": 5,
    },
    {
        "title": "Software Engineering Intern",
        "description": "We offer a structured internship for computer science students to work on real product features alongside our experienced engineering team.",
        "responsibilities": "Develop features under senior developer guidance\nWrite unit tests for assigned features\nParticipate in code reviews and sprint meetings\nDocument code and processes",
        "requirements": "Currently pursuing CS or related degree\nBasic Python or JavaScript knowledge\nFamiliarity with Git\nProblem-solving mindset",
        "skills": "Python, JavaScript, Git, HTML, CSS, Problem Solving",
        "job_type": "internship", "work_mode": "hybrid", "experience_level": "entry",
        "salary_min": 4, "salary_max": 6,
    },
    {
        "title": "Technical Writer",
        "description": "We need a technical writer to create clear, accurate, and developer-friendly documentation for our APIs and internal systems.",
        "responsibilities": "Write and maintain API documentation\nCreate user guides and tutorials\nCollaborate with engineering on accuracy\nManage documentation versioning",
        "requirements": "2+ years technical writing experience\nExperience documenting APIs (OpenAPI/Swagger)\nStrong English writing skills\nFamiliarity with developer tools",
        "skills": "Technical Writing, API Documentation, Markdown, OpenAPI, GitHub, Confluence",
        "job_type": "full_time", "work_mode": "remote", "experience_level": "mid",
        "salary_min": 7, "salary_max": 14,
    },
    {
        "title": "Sales Development Representative",
        "description": "Drive growth by identifying and nurturing new business opportunities through outbound prospecting and lead qualification.",
        "responsibilities": "Prospect and qualify new leads\nConduct outreach via email, phone, and LinkedIn\nSchedule demos for the sales team\nMaintain CRM data accuracy",
        "requirements": "1+ years sales or SDR experience\nExcellent verbal and written communication\nExperience with CRM tools like Salesforce or HubSpot\nResilient and goal-oriented mindset",
        "skills": "Sales, CRM, Salesforce, HubSpot, Communication, Lead Generation",
        "job_type": "full_time", "work_mode": "onsite", "experience_level": "entry",
        "salary_min": 5, "salary_max": 10,
    },
]

CANDIDATE_FIRST_NAMES = [
    "Aarav", "Aisha", "Arjun", "Ananya", "Aditi", "Amit", "Anjali", "Aditya",
    "Bhavya", "Bunty", "Chetan", "Deepika", "Dinesh", "Divya", "Esha",
    "Farhan", "Gaurav", "Geeta", "Hardik", "Harini", "Ishaan", "Isha",
    "Jatin", "Juhi", "Karan", "Kavya", "Kiran", "Kritika", "Lakshmi",
    "Manish", "Meera", "Mihir", "Muskan", "Naman", "Neha", "Nikhil",
    "Pankaj", "Pooja", "Priya", "Rahul", "Rajat", "Rajeev", "Raksha",
    "Ravi", "Ritika", "Rohan", "Ruchi", "Sachin", "Samaira", "Sanjay",
    "Sara", "Seema", "Shivam", "Shreya", "Siddharth", "Simran", "Smita",
    "Suresh", "Tanvi", "Tanya", "Tarun", "Urvashi", "Utkarsh", "Varun",
    "Vibha", "Vijay", "Vikas", "Vinay", "Vineeta", "Vishal", "Yash",
    "Yogesh", "Zara", "Akash", "Alisha", "Balaji", "Chaitra", "Disha",
    "Ekta", "Ganesh", "Hemant", "Indira", "Jagdish", "Ketki", "Lavanya",
    "Mahesh", "Nisha", "Omkar", "Pallavi", "Qureshi", "Ramesh", "Sarika",
    "Tejas", "Ujjwal", "Vaishnavi", "Waqar", "Ximena", "Yuvraj", "Zeenat",
]

CANDIDATE_LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Singh", "Kumar", "Patel", "Mehta", "Joshi",
    "Iyer", "Reddy", "Nair", "Rao", "Bhat", "Shah", "Jain", "Agarwal",
    "Mishra", "Tiwari", "Pandey", "Kapoor", "Malhotra", "Khanna", "Sinha",
    "Das", "Roy", "Sen", "Banerjee", "Chakraborty", "Mukherjee", "Bose",
]

CITIES = [
    "Bangalore", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Pune",
    "Kolkata", "Ahmedabad", "Jaipur", "Noida", "Gurgaon", "Kochi",
]

SKILLS_POOL = [
    "Python, Django, REST APIs, PostgreSQL, Docker",
    "JavaScript, React, Node.js, MongoDB, AWS",
    "Java, Spring Boot, Microservices, Kafka, MySQL",
    "Data Analysis, SQL, Tableau, Power BI, Excel",
    "Machine Learning, Python, scikit-learn, TensorFlow, NLP",
    "Android, Kotlin, Java, Firebase, MVVM",
    "iOS, Swift, SwiftUI, Xcode, REST APIs",
    "DevOps, Docker, Kubernetes, AWS, Terraform, CI/CD",
    "Cybersecurity, OWASP, Penetration Testing, SIEM, Linux",
    "Product Management, Agile, JIRA, Analytics, SQL",
    "UX Design, Figma, Prototyping, User Research, CSS",
    "Backend Engineering, Go, gRPC, PostgreSQL, Redis",
    "Full Stack, Node.js, React, PostgreSQL, TypeScript",
    "Business Analysis, Agile, Process Mapping, SQL, Excel",
    "Cloud Engineering, AWS, GCP, Terraform, Python",
    "Data Engineering, Spark, Hadoop, Airflow, SQL, Python",
    "QA Automation, Selenium, Playwright, Python, Pytest",
    "Frontend, Vue.js, HTML, CSS, JavaScript, TypeScript",
    "Sales, CRM, Salesforce, HubSpot, Communication",
    "Technical Writing, API Docs, Markdown, Confluence",
]

RESUME_TEMPLATES = [
    """OBJECTIVE
Experienced {role} with {yoe} years of experience building scalable systems. Passionate about clean code and impactful products.

SKILLS
{skills}

EXPERIENCE
{company_b}, {city} — {role}
{start} – Present
• Designed and implemented core product features used by 50,000+ users
• Reduced API response times by 40% through query optimization
• Led a team of 4 engineers through successful product launches
• Introduced automated testing, achieving 85% code coverage

{company_a}, {city} — Junior {role}
{start2} – {start}
• Developed RESTful APIs consumed by web and mobile clients
• Collaborated with cross-functional teams on product delivery
• Resolved critical bugs reducing customer-reported issues by 30%

EDUCATION
B.Tech in Computer Science Engineering
{university}, {city} — {grad_year}
CGPA: {gpa}/10

CERTIFICATIONS
• {cert1}
• {cert2}

ACHIEVEMENTS
• Top performer award, {company_b} ({start})
• Contributed to open source project with 2,000+ GitHub stars
""",

    """PROFESSIONAL SUMMARY
Results-driven {role} with {yoe} years in fast-paced product companies. Strong background in {skills_short}.

TECHNICAL SKILLS
{skills}

WORK EXPERIENCE
{company_b} | {role} | {city}
{start} – Present
• Built scalable backend services handling 1M+ requests/day
• Integrated third-party APIs and payment gateways
• Mentored 2 junior engineers in best practices
• Improved deployment frequency from monthly to weekly releases

{company_a} | Associate {role} | {city}
{start2} – {start}
• Contributed to rewriting legacy monolith to microservices
• Developed unit and integration test suites
• Participated in bi-weekly design reviews

EDUCATION
Bachelor of Engineering — {university}, {grad_year}

LANGUAGES
English (Fluent), Hindi (Native)

INTERESTS
Open source development, technical blogging, hackathons
""",

    """CAREER PROFILE
Motivated {role} with {yoe}+ years of hands-on industry experience. Expertise in {skills_short}.

KEY SKILLS
{skills}

PROFESSIONAL EXPERIENCE
{company_b} — {role} ({start} to Present)
Location: {city}
Responsibilities:
- Architected and delivered major platform features on time
- Drove adoption of microservices architecture saving 25% infrastructure cost
- Conducted 50+ technical interviews for engineering roles
- Established team coding standards and documentation practices

{company_a} — Junior {role} ({start2} to {start})
Location: {city}
- Developed and tested REST APIs for mobile and web clients
- Managed deployments on AWS EC2 and S3
- Resolved production incidents with zero SLA breach in 18 months

EDUCATIONAL QUALIFICATIONS
• B.Tech CSE — {university} ({grad_year})
• Higher Secondary — Delhi Public School ({hs_year})

PROFESSIONAL CERTIFICATIONS
• {cert1}
• {cert2}
""",
]

CERTIFICATIONS = [
    "AWS Certified Solutions Architect – Associate",
    "Google Professional Data Engineer",
    "Microsoft Azure Fundamentals (AZ-900)",
    "Oracle Java SE 11 Developer",
    "Certified Kubernetes Administrator (CKA)",
    "Google Associate Cloud Engineer",
    "Meta React Developer Certificate",
    "MongoDB Certified Developer",
    "Cisco CCNA",
    "ISTQB Foundation Level",
    "PMI Agile Certified Practitioner (PMI-ACP)",
    "Scrum Master Certified (SMC)",
    "Tableau Desktop Specialist",
    "TensorFlow Developer Certificate",
    "CEH – Certified Ethical Hacker",
]

UNIVERSITIES = [
    "IIT Bombay", "IIT Delhi", "IIT Madras", "IIT Bangalore", "NIT Trichy",
    "BITS Pilani", "VIT Vellore", "SRM Institute", "Manipal University",
    "Pune University", "Anna University", "Osmania University",
    "Delhi University", "Jadavpur University", "IIIT Hyderabad",
]

PREVIOUS_COMPANIES = [
    "Infosys", "Wipro", "TCS", "HCL Technologies", "Cognizant",
    "Capgemini", "IBM India", "Accenture", "Tech Mahindra", "Mphasis",
    "Freshworks", "Zoho Corp", "Mu Sigma", "Fractal Analytics", "Publicis Sapient",
]

COVER_NOTES = [
    "I'm very excited about this opportunity and believe my background in {skills_short} aligns perfectly with your requirements.",
    "Having worked in similar environments, I'm confident I can add immediate value to your team. Looking forward to discussing further.",
    "Your mission resonates strongly with my professional goals. I'd love to bring my expertise in {skills_short} to help achieve your targets.",
    "I've been following your company's growth and am eager to contribute. My experience with {skills_short} makes me a strong fit.",
    "This role is perfectly aligned with my career trajectory. I'm excited about the challenge and ready to make an impact from day one.",
    None,  # Some candidates don't write cover notes
    None,
]

APP_STATUSES = [
    "applied", "applied", "applied",         # Most common
    "under_review", "under_review",
    "shortlisted",
    "interview",
    "rejected",
    "hired",
]


def random_date(start_days_ago=400, end_days_ago=10):
    delta = random.randint(end_days_ago, start_days_ago)
    return datetime.utcnow() - timedelta(days=delta)


def make_resume_text(candidate_name, skills_str, city):
    template = random.choice(RESUME_TEMPLATES)
    yoe = random.randint(1, 10)
    role_parts = skills_str.split(",")
    role = role_parts[0].strip() if role_parts else "Software Engineer"
    skills_short = ", ".join(s.strip() for s in role_parts[:3])

    company_a = random.choice(PREVIOUS_COMPANIES)
    company_b = random.choice([c for c in PREVIOUS_COMPANIES if c != company_a])

    base_year = 2024 - yoe
    start = f"{base_year}"
    start2 = f"{base_year - random.randint(1, 3)}"
    grad_year = base_year - random.randint(0, 2)
    hs_year = grad_year - 2
    university = random.choice(UNIVERSITIES)
    gpa = round(random.uniform(6.5, 9.8), 1)
    cert1 = random.choice(CERTIFICATIONS)
    cert2 = random.choice([c for c in CERTIFICATIONS if c != cert1])

    return template.format(
        role=role, yoe=yoe, skills=skills_str, skills_short=skills_short,
        company_a=company_a, company_b=company_b,
        city=city, start=start, start2=start2,
        grad_year=grad_year, hs_year=hs_year,
        university=university, gpa=gpa,
        cert1=cert1, cert2=cert2,
    )


# ─────────────────────────────────────────────
# SEEDING
# ─────────────────────────────────────────────

with app.app_context():
    db.create_all()
    print("=" * 60)
    print("  Zentra Rich Seed — Starting")
    print("=" * 60)

    # ── 1. Companies / Recruiters ──────────────────────────────
    print("\n[1/4] Creating 15 companies & recruiter accounts...")
    recruiter_profiles = []
    for i, co in enumerate(COMPANIES):
        email = f"hiring@{co['name'].lower().replace(' ', '').replace(',', '')}.example.com"
        user = User.query.filter_by(email=email).first()
        if not user:
            contact = CONTACT_NAMES[i]
            user = User(
                full_name=contact,
                email=email,
                role=User.ROLE_RECRUITER,
            )
            user.set_password("SampleRecruiter123!")
            db.session.add(user)
            db.session.flush()

            profile = RecruiterProfile(
                user_id=user.id,
                company_name=co["name"],
                industry=co["industry"],
                company_size=co["size"],
                company_website=co["website"],
                contact_role="Talent Acquisition Manager",
                phone=f"+91 98{random.randint(10000000, 99999999)}",
                approval_status=RecruiterProfile.STATUS_APPROVED,
            )
            db.session.add(profile)
            db.session.flush()
            recruiter_profiles.append(profile)
            print(f"  [+] {co['name']} [{co['industry']}]")
        else:
            rp = user.recruiter_profile
            if rp:
                recruiter_profiles.append(rp)
            print(f"  [-] {co['name']} already exists, skipped")

    db.session.commit()
    print(f"  -> {len(recruiter_profiles)} recruiter profiles ready")

    # ── 2. 100 Job Postings ────────────────────────────────────
    print("\n[2/4] Creating 100 job postings...")
    jobs_created = []
    jobs_per_company = 100 // len(recruiter_profiles)
    extra = 100 % len(recruiter_profiles)

    for idx, rp in enumerate(recruiter_profiles):
        count = jobs_per_company + (1 if idx < extra else 0)
        for _ in range(count):
            jt = random.choice(JOB_TEMPLATES)
            # Vary the title slightly to avoid duplicates
            suffix = random.choice(["", " (Remote)", " - India", " - Contract", ""])
            title = jt["title"] + suffix

            status_roll = random.random()
            if status_roll < 0.70:
                status = "active"
            elif status_roll < 0.82:
                status = "paused"
            elif status_roll < 0.92:
                status = "closed"
            else:
                status = "draft"

            job = Job(
                recruiter_profile_id=rp.id,
                title=title,
                description=jt["description"],
                responsibilities=jt["responsibilities"],
                requirements=jt["requirements"],
                job_type=jt["job_type"],
                work_mode=jt["work_mode"],
                experience_level=jt["experience_level"],
                location=f"{rp.company_name.split()[0]} HQ, {random.choice(CITIES)}",
                salary_min=jt["salary_min"],
                salary_max=jt["salary_max"],
                status=status,
                created_at=random_date(300, 5),
            )
            db.session.add(job)
            db.session.flush()
            jobs_created.append(job)

    db.session.commit()
    print(f"  -> {len(jobs_created)} jobs created")

    # ── 3. 100 Candidates with Resumes ────────────────────────
    print("\n[3/4] Creating 100 candidates with resumes...")
    candidates_created = []
    used_names = set()

    for i in range(100):
        while True:
            first = random.choice(CANDIDATE_FIRST_NAMES)
            last = random.choice(CANDIDATE_LAST_NAMES)
            full_name = f"{first} {last}"
            if full_name not in used_names:
                used_names.add(full_name)
                break

        email = f"{first.lower()}.{last.lower()}{random.randint(10, 99)}@example.com"
        if User.query.filter_by(email=email).first():
            continue

        city = random.choice(CITIES)
        skills = random.choice(SKILLS_POOL)
        resume_text = make_resume_text(full_name, skills, city)
        ats_score = round(random.uniform(35, 95), 1)

        user = User(
            full_name=full_name,
            email=email,
            role=User.ROLE_CANDIDATE,
            headline=skills.split(",")[0].strip() + " Professional",
            location=city,
            skills=skills,
        )
        user.set_password("Candidate@123")
        db.session.add(user)
        db.session.flush()

        resume = Resume(
            candidate_id=user.id,
            source="paste",
            raw_text=resume_text,
            name=f"{full_name} - Resume",
            target_role=skills.split(",")[0].strip(),
            last_ats_score=ats_score,
            last_matched_keywords=", ".join(skills.split(",")[:4]).strip(),
            last_missing_keywords=random.choice([
                "leadership, project management",
                "cloud architecture, system design",
                "agile, scrum, JIRA",
                "data structures, algorithms",
                "",
            ]),
            created_at=random_date(400, 30),
        )
        db.session.add(resume)
        db.session.flush()
        candidates_created.append((user, resume))

    db.session.commit()
    print(f"  -> {len(candidates_created)} candidates with resumes created")

    # ── 4. ~300 Applications ───────────────────────────────────
    print("\n[4/4] Creating applications...")
    active_jobs = [j for j in jobs_created if j.status in ("active", "closed", "paused")]
    apps_created = 0
    applied_pairs = set()

    for candidate, resume in candidates_created:
        # Each candidate applies to 2–5 jobs
        num_apps = random.randint(2, 5)
        eligible_jobs = random.sample(active_jobs, min(num_apps, len(active_jobs)))

        for job in eligible_jobs:
            pair = (job.id, candidate.id)
            if pair in applied_pairs:
                continue
            applied_pairs.add(pair)

            status = random.choice(APP_STATUSES)
            cover_template = random.choice(COVER_NOTES)
            skills_short = ", ".join((candidate.skills or "").split(",")[:2]).strip()
            cover = cover_template.format(skills_short=skills_short) if cover_template else None

            app = Application(
                job_id=job.id,
                candidate_id=candidate.id,
                resume_id=resume.id,
                match_score=round(random.uniform(30, 98), 1),
                cover_note=cover,
                status=status,
                applied_at=random_date(200, 1),
            )
            db.session.add(app)
            apps_created += 1

    db.session.commit()

    print(f"  -> {apps_created} applications created")

    # ── Summary ────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  Zentra Rich Seed - Complete!")
    print("=" * 60)
    print(f"  Companies / Recruiters : {len(recruiter_profiles)}")
    print(f"  Job postings           : {len(jobs_created)}")
    print(f"  Candidates             : {len(candidates_created)}")
    print(f"  Applications           : {apps_created}")
    print()
    print("  Recruiter login password : SampleRecruiter123!")
    print("  Candidate login password : Candidate@123")
    print("  Admin login              : admin@zentra.example.com / Admin@123")
    print("=" * 60)
