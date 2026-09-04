"""Taxonomy, normalization mappings, weighted skill relationships, and noise blacklists
for ATS extraction and matching.
"""

from typing import Dict, Set

# Structured Taxonomy Categories
LANGUAGES: Set[str] = {
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "C", "Go", "Golang",
    "Rust", "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "Dart", "SQL", "HTML",
    "CSS", "Sass", "SCSS", "Bash", "Shell", "PowerShell", "MATLAB",
}

FRAMEWORKS: Set[str] = {
    "Flask", "Django", "FastAPI", "Tornado", "Bottle", "Pyramid",
    "React", "React.js", "React Native", "Next.js", "Vue", "Vue.js", "Nuxt.js",
    "Angular", "Svelte", "SvelteKit", "Express", "Express.js", "NestJS", "Node.js",
    "Spring", "Spring Boot", "ASP.NET", ".NET Core", "Laravel", "Ruby on Rails",
    "PyTorch", "TensorFlow", "Keras", "Scikit-Learn", "Pandas", "NumPy", "SciPy",
    "OpenCV", "Hugging Face", "LangChain", "LlamaIndex",
    "SQLAlchemy", "Hibernate", "Prisma", "TypeORM", "Mongoose", "Entity Framework",
    "Tailwind CSS", "Bootstrap", "Material-UI", "Chakra UI", "Redux", "Zustand",
}

DATABASES: Set[str] = {
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "MariaDB", "Oracle DB",
    "Microsoft SQL Server", "Cassandra", "DynamoDB", "Elasticsearch", "CouchDB",
    "Neo4j", "Firebase", "Supabase", "Snowflake", "BigQuery", "Redshift", "ClickHouse",
}

TOOLS: Set[str] = {
    "Git", "GitHub", "GitLab", "Bitbucket", "Jira", "Confluence", "Postman",
    "Swagger", "VS Code", "Vim", "PyCharm", "IntelliJ", "Figma", "Canva", "Tableau",
    "Power BI", "Excel", "HRMS", "Salesforce", "SolidWorks", "AutoCAD", "ANSYS",
    "Docker", "Kubernetes", "Podman", "Helm", "Terraform", "Ansible", "Puppet", "Chef",
    "Jenkins", "GitHub Actions", "GitLab CI", "CircleCI", "ArgoCD",
    "Prometheus", "Grafana", "Datadog", "CloudWatch", "Kafka", "RabbitMQ", "Celery",
    "Linux", "Ubuntu", "Debian", "CentOS", "Nginx", "Apache",
    "AWS", "Amazon Web Services", "GCP", "Google Cloud", "Azure", "Microsoft Azure",
    "Apache Spark", "Spark", "Delta Lake", "Azure Data Lake", "Databricks", "Azure Synapse",
    "Playwright", "JMeter", "Chaos Mesh", "Azure Cosmos DB",
}

TECHNICAL_PRACTICES: Set[str] = {
    "REST APIs", "GraphQL", "gRPC", "WebSockets", "Microservices", "Serverless",
    "Database Schema Design", "SQL/Query Optimization",
    "Code Review", "Testing", "Unit Testing", "Integration Testing", "TDD", "Automated Testing",
    "Data Structures", "Algorithms", "Object-Oriented Programming", "OOP",
    "System Architecture", "System Design", "Agile", "Scrum", "Kanban",
    "Cloud Architecture", "Distributed Systems", "Observability", "SRE", "Site Reliability Engineering",
    "Zero Trust", "FinOps", "Cybersecurity", "Developer Experience", "Product Management",
    "API Design", "Test Automation", "Performance Testing", "Design Systems", "Web Performance",
    "Core Web Vitals", "Micro-frontends", "Chaos Engineering",
    "Machine Learning", "Deep Learning", "Natural Language Processing",
    "Computer Vision", "Data Analysis", "Data Visualization", "A/B Testing",
    "ETL", "Data Pipelines", "Feature Engineering", "Responsive Design",
    "CI/CD",
}

# Unified Technical Skills = Languages + Frameworks + Databases + Tools + Technical Practices
TECHNICAL_SKILLS: Set[str] = LANGUAGES | FRAMEWORKS | DATABASES | TOOLS | TECHNICAL_PRACTICES

SOFT_SKILLS: Set[str] = {
    "Communication", "Leadership", "Team Collaboration", "Problem Solving",
    "Critical Thinking", "Stakeholder Management", "Project Management",
    "Recruitment", "Talent Acquisition", "Onboarding", "Payroll", "Employee Engagement",
    "Conflict Resolution", "SEO", "Search Engine Optimization", "Content Strategy",
    "Email Marketing", "Brand Management", "Branding", "Google Analytics",
    "6 Sigma", "Six Sigma", "GD&T", "Thermodynamics", "Quality Control",
    "Product Design", "Manufacturing", "Forecasting", "Requirements Gathering",
}

CERTIFICATIONS: Set[str] = {
    "AWS Certified", "AWS Solutions Architect", "CKA", "CKAD", "PMP",
    "Scrum Master", "CSM", "CISSP", "GCP Professional Cloud Architect",
    "Azure Solutions Architect", "Six Sigma Green Belt", "Six Sigma Black Belt",
}

# Categorized taxonomy dictionary for structured routing
STRUCTURED_CATEGORIES = {
    "languages": LANGUAGES,
    "frameworks": FRAMEWORKS,
    "databases": DATABASES,
    "tools": TOOLS,
    "technical_skills": TECHNICAL_SKILLS,
    "soft_skills": SOFT_SKILLS,
    "certifications": CERTIFICATIONS,
}

# Mapping aliases and variations to canonical skill names
SKILL_ALIASES: Dict[str, str] = {
    # Python & Frameworks
    "python": "Python",
    "python 3": "Python",
    "python3": "Python",
    "python programming": "Python",
    "flask": "Flask",
    "flask framework": "Flask",
    "flask py": "Flask",
    "fastapi": "FastAPI",
    "fast api": "FastAPI",
    "django": "Django",
    "django rest framework": "Django",
    "drf": "Django",
    "sqlalchemy": "SQLAlchemy",
    "sqlalchemy orm": "SQLAlchemy",
    "express": "Express",
    "express.js": "Express",
    "expressjs": "Express",
    "node": "Node.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "spring": "Spring",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",

    # Frontend
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "react native": "React Native",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "next js": "Next.js",
    "vue": "Vue",
    "vue.js": "Vue",
    "vuejs": "Vue",
    "angular": "Angular",
    "angularjs": "Angular",
    "svelte": "Svelte",
    "sveltekit": "SvelteKit",
    "tailwind": "Tailwind CSS",
    "tailwind css": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "bootstrap": "Bootstrap",
    "html": "HTML",
    "html5": "HTML",
    "css": "CSS",
    "css3": "CSS",
    "sass": "Sass",
    "scss": "SCSS",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "redux": "Redux",

    # Databases
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "postgresql db": "PostgreSQL",
    "postgresql database": "PostgreSQL",
    "psql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "redis": "Redis",
    "sqlite": "SQLite",
    "sql server": "Microsoft SQL Server",
    "ms sql": "Microsoft SQL Server",
    "mssql": "Microsoft SQL Server",
    "dynamodb": "DynamoDB",
    "cassandra": "Cassandra",
    "elasticsearch": "Elasticsearch",
    "snowflake": "Snowflake",
    "bigquery": "BigQuery",
    "sql": "SQL",

    # Cloud & DevOps
    "aws": "AWS",
    "amazon web services": "AWS",
    "aws cloud": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "docker": "Docker",
    "docker containers": "Docker",
    "docker container": "Docker",
    "dockerization": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "ci/cd": "CI/CD",
    "ci cd": "CI/CD",
    "cicd": "CI/CD",
    "ci/cd pipeline": "CI/CD",
    "ci/cd pipelines": "CI/CD",
    "continuous integration": "CI/CD",
    "continuous deployment": "CI/CD",
    "jenkins": "Jenkins",
    "github actions": "GitHub Actions",
    "gitlab ci": "GitLab CI",
    "linux": "Linux",
    "bash": "Bash",
    "shell scripting": "Bash",
    "prometheus": "Prometheus",
    "grafana": "Grafana",
    "git": "Git",
    "github": "GitHub",

    # Engineering Concepts & Practices
    "rest": "REST APIs",
    "rest api": "REST APIs",
    "rest apis": "REST APIs",
    "restful api": "REST APIs",
    "restful apis": "REST APIs",
    "restful web services": "REST APIs",
    "rest services": "REST APIs",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "microservices": "Microservices",
    "microservices architecture": "Microservices",
    "database design": "Database Schema Design",
    "database designs": "Database Schema Design",
    "database schema design": "Database Schema Design",
    "database schema": "Database Schema Design",
    "database schemas": "Database Schema Design",
    "db design": "Database Schema Design",
    "schema design": "Database Schema Design",
    "query optimization": "SQL/Query Optimization",
    "query optimizations": "SQL/Query Optimization",
    "sql optimization": "SQL/Query Optimization",
    "sql optimizations": "SQL/Query Optimization",
    "sql/query optimization": "SQL/Query Optimization",
    "query tuning": "SQL/Query Optimization",
    "code review": "Code Review",
    "code reviews": "Code Review",
    "peer review": "Code Review",
    "testing": "Testing",
    "unit test": "Unit Testing",
    "unit tests": "Unit Testing",
    "unit testing": "Unit Testing",
    "automated testing": "Automated Testing",
    "tdd": "TDD",
    "test driven development": "TDD",
    "data structures": "Data Structures",
    "algorithms": "Algorithms",
    "oop": "OOP",
    "object oriented programming": "OOP",
    "object-oriented programming": "OOP",
    "system design": "System Design",
    "system architecture": "System Architecture",
    "cloud architecture": "Cloud Architecture",
    "cloud architect": "Cloud Architecture",
    "cloud solution architect": "Cloud Architecture",
    "cloud solutions architect": "Cloud Architecture",
    "cloud infrastructure": "Cloud Architecture",
    "distributed systems": "Distributed Systems",
    "distributed architecture": "Distributed Systems",
    "distributed computing": "Distributed Systems",
    "observability": "Observability",
    "monitoring & observability": "Observability",
    "sre": "SRE",
    "site reliability engineering": "Site Reliability Engineering",
    "site reliability engineer": "Site Reliability Engineering",
    "zero trust": "Zero Trust",
    "finops": "FinOps",
    "cloud cost optimization": "FinOps",
    "cybersecurity": "Cybersecurity",
    "threat intelligence": "Cybersecurity",
    "developer experience": "Developer Experience",
    "product management": "Product Management",
    "api design": "API Design",
    "test automation": "Test Automation",
    "performance testing": "Performance Testing",
    "design systems": "Design Systems",
    "web performance": "Web Performance",
    "core web vitals": "Core Web Vitals",
    "micro-frontends": "Micro-frontends",
    "microfrontends": "Micro-frontends",
    "chaos engineering": "Chaos Engineering",
    "spark": "Apache Spark",
    "apache spark": "Apache Spark",
    "delta lake": "Delta Lake",
    "azure data lake": "Azure Data Lake",
    "databricks": "Databricks",
    "synapse": "Azure Synapse",
    "azure synapse": "Azure Synapse",
    "playwright": "Playwright",
    "jmeter": "JMeter",
    "cosmos db": "Azure Cosmos DB",
    "azure cosmos db": "Azure Cosmos DB",
    "responsive design": "Responsive Design",

    # Data Science & ML
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "deep learning": "Deep Learning",
    "natural language processing": "Natural Language Processing",
    "nlp": "Natural Language Processing",
    "computer vision": "Computer Vision",
    "cv": "Computer Vision",
    "data analysis": "Data Analysis",
    "data analytics": "Data Analysis",
    "data visualization": "Data Visualization",
    "a/b testing": "A/B Testing",
    "ab testing": "A/B Testing",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scikit-learn": "Scikit-Learn",
    "sklearn": "Scikit-Learn",
    "scikitlearn": "Scikit-Learn",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "power bi": "Power BI",
    "powerbi": "Power BI",
    "tableau": "Tableau",
    "excel": "Excel",
    "microsoft excel": "Excel",

    # Management / Soft Skills / Non-Tech Domains
    "agile": "Agile",
    "scrum": "Scrum",
    "kanban": "Kanban",
    "jira": "Jira",
    "confluence": "Confluence",
    "communication": "Communication",
    "leadership": "Leadership",
    "team leadership": "Leadership",
    "team collaboration": "Team Collaboration",
    "problem solving": "Problem Solving",
    "stakeholder management": "Stakeholder Management",
    "project management": "Project Management",
    "requirements gathering": "Requirements Gathering",
    "recruitment": "Recruitment",
    "talent acquisition": "Recruitment",
    "onboarding": "Onboarding",
    "payroll": "Payroll",
    "hrms": "HRMS",
    "employee engagement": "Employee Engagement",
    "conflict resolution": "Conflict Resolution",
    "seo": "SEO",
    "search engine optimization": "SEO",
    "branding": "Branding",
    "canva": "Canva",
    "google analytics": "Google Analytics",
    "email marketing": "Email Marketing",
    "content strategy": "Content Strategy",
    "solidworks": "SolidWorks",
    "autocad": "AutoCAD",
    "cad": "AutoCAD",
    "ansys": "ANSYS",
    "6 sigma": "6 Sigma",
    "six sigma": "6 Sigma",
    "gd&t": "GD&T",
    "thermodynamics": "Thermodynamics",
    "product design": "Product Design",
    "quality control": "Quality Control",
    "manufacturing": "Manufacturing",
    "forecasting": "Forecasting",

    # Certifications
    "aws certified": "AWS Certified",
    "aws solutions architect": "AWS Solutions Architect",
    "certified kubernetes administrator": "CKA",
    "cka": "CKA",
    "pmp": "PMP",
    "certified scrum master": "Scrum Master",
    "csm": "Scrum Master",
}

# Weighted relationship graph: maps canonical skill -> dict of related skills with relationship strength (0.0 - 1.0)
# 0.80-0.85 = Strong related (e.g. FastAPI ↔ Flask)
# 0.60-0.70 = Moderate related (e.g. Django ↔ Flask)
# 0.00 = Unrelated (e.g. React ↔ Flask)
SKILL_RELATIONSHIPS: Dict[str, Dict[str, float]] = {
    # Python Web Frameworks
    "Flask": {"FastAPI": 0.80, "Django": 0.65, "Tornado": 0.60, "Bottle": 0.60},
    "FastAPI": {"Flask": 0.80, "Django": 0.65, "Tornado": 0.60},
    "Django": {"Flask": 0.65, "FastAPI": 0.65},

    # JS Frontend Frameworks
    "React": {"Next.js": 0.85, "Vue": 0.70, "Angular": 0.60, "Svelte": 0.65},
    "Next.js": {"React": 0.85, "Nuxt.js": 0.70, "SvelteKit": 0.65},
    "Vue": {"React": 0.70, "Angular": 0.65, "Svelte": 0.65, "Nuxt.js": 0.80},
    "Angular": {"React": 0.60, "Vue": 0.65, "Svelte": 0.60},
    "Svelte": {"React": 0.65, "Vue": 0.65, "Angular": 0.60},

    # Backend JS Frameworks
    "Express": {"NestJS": 0.75, "Node.js": 0.80, "FastAPI": 0.50, "Flask": 0.50},
    "NestJS": {"Express": 0.75, "Spring Boot": 0.65, "Node.js": 0.80},

    # Relational Databases
    "PostgreSQL": {"MySQL": 0.80, "MariaDB": 0.75, "SQLite": 0.70, "Microsoft SQL Server": 0.70, "Oracle DB": 0.65},
    "MySQL": {"PostgreSQL": 0.80, "MariaDB": 0.85, "SQLite": 0.70, "Microsoft SQL Server": 0.70},
    "SQLite": {"PostgreSQL": 0.70, "MySQL": 0.70},
    "Microsoft SQL Server": {"PostgreSQL": 0.70, "MySQL": 0.70, "Oracle DB": 0.75},

    # NoSQL Databases
    "MongoDB": {"DynamoDB": 0.70, "Cassandra": 0.65, "CouchDB": 0.70, "Redis": 0.55},
    "DynamoDB": {"MongoDB": 0.70, "Cassandra": 0.65, "Redis": 0.55},
    "Cassandra": {"MongoDB": 0.65, "DynamoDB": 0.65},

    # Cloud Providers
    "AWS": {"GCP": 0.75, "Azure": 0.75},
    "GCP": {"AWS": 0.75, "Azure": 0.75},
    "Azure": {"AWS": 0.75, "GCP": 0.75},

    # Container / Orchestration
    "Docker": {"Podman": 0.85, "Kubernetes": 0.50},
    "Kubernetes": {"Docker": 0.50, "Docker Swarm": 0.70},

    # CI/CD
    "Jenkins": {"GitHub Actions": 0.80, "GitLab CI": 0.80, "CircleCI": 0.75},
    "GitHub Actions": {"Jenkins": 0.80, "GitLab CI": 0.85, "CircleCI": 0.75},
    "GitLab CI": {"Jenkins": 0.80, "GitHub Actions": 0.85, "CircleCI": 0.75},

    # Deep Learning Frameworks
    "PyTorch": {"TensorFlow": 0.80, "Keras": 0.70},
    "TensorFlow": {"PyTorch": 0.80, "Keras": 0.80},
    "Keras": {"PyTorch": 0.70, "TensorFlow": 0.80},

    # BI & Viz Tools
    "Power BI": {"Tableau": 0.80, "Excel": 0.50},
    "Tableau": {"Power BI": 0.80, "Excel": 0.50},

    # Testing
    "Unit Testing": {"Testing": 0.90, "Automated Testing": 0.80, "TDD": 0.75},
    "Testing": {"Unit Testing": 0.90, "Automated Testing": 0.85, "Integration Testing": 0.85},
    "Automated Testing": {"Testing": 0.85, "Unit Testing": 0.80, "Integration Testing": 0.80},

    # Database concepts
    "Database Schema Design": {"Database Design": 1.0, "SQL/Query Optimization": 0.60},
    "SQL/Query Optimization": {"Database Schema Design": 0.60},
}


def get_skill_relationship_strength(required_skill: str, candidate_skill: str) -> float:
    """Return relationship strength between 0.0 (unrelated) and 1.0 (exact/synonym)."""
    if required_skill == candidate_skill:
        return 1.0
    return SKILL_RELATIONSHIPS.get(required_skill, {}).get(candidate_skill, 0.0)


# Strict Noise Blacklist: Words, generic verbs, adjectives, company words, job titles,
# conversational fillers that MUST NEVER be identified as skills
NOISE_WORDS: Set[str] = {
    # Company / generic job words
    "nexova", "company", "startup", "organization", "team", "fast-moving", "small",
    "large", "product", "core", "platform", "looking", "seeking", "hire", "hiring",
    "role", "job", "position", "candidate", "applicant", "ideal", "successful",
    "engineer", "developer", "backend", "frontend", "fullstack", "architect",
    "intern", "lead", "senior", "junior", "staff", "associate", "specialist",
    "manager", "head", "director", "vp", "executive",

    # Generic verbs
    "build", "maintain", "powering", "work", "working", "develop", "developing",
    "design", "designing", "help", "helping", "create", "creating", "drive",
    "delivering", "deliver", "scale", "scaling", "manage", "managing", "join",
    "collaborate", "collaborating", "implement", "implementing", "write", "writing",
    "ensure", "ensuring", "support", "supporting", "learn", "learning", "participate",
    "participating", "contribute", "contributing", "ship", "shipping", "handle",
    "handling", "focus", "focusing", "optimize", "optimizing", "solve", "solving",

    # Generic adjectives / conversational words
    "strong", "high", "good", "great", "excellent", "deep", "solid", "proven",
    "passion", "passionate", "excited", "energetic", "motivated", "dynamic",
    "collaborative", "smart", "innovative", "hands-on", "flexible", "able",
    "ability", "background", "knowledge", "experience", "experienced", "years",
    "year", "skills", "skill", "requirements", "required", "preferred", "bonus",
    "plus", "nice", "responsibilities", "qualifications", "education", "degree",
    "summary", "about", "overview", "mission", "values", "culture", "benefits",
    "perks", "competitive", "salary", "equity", "remote", "hybrid", "onsite",
    "location", "full-time", "part-time", "contract", "daily", "weekly", "monthly",
    "people", "user", "users", "customer", "customers", "client", "clients",
    "business", "industry", "market", "environment", "ecosystem", "stack",
    "solution", "solutions", "system", "systems", "service", "services",
    "feature", "features", "tool", "tools", "technology", "technologies",
    "world", "today", "future", "best", "practices", "standard", "standards",
    "clean", "quality", "modern", "scalable", "efficient", "robust", "secure",
    "etc", "including", "using", "with", "and", "or", "to", "for", "in", "on",
    "at", "of", "from", "by", "as", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "can", "could", "should", "would",
    "will", "shall", "may", "might", "must", "you", "your", "our", "we", "they",
    "them", "their", "it", "its", "this", "that", "these", "those",
}
