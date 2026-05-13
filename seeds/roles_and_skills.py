"""
Seed script — roles, skills, and role-skill mappings.

Usage:
    python -m seeds.roles_and_skills

Structure
---------
Three-level hierarchy (matches the new role_type column):

  field  → top-level domain shown in the UI  (IT, Engineering, Business)
  domain → mid-level grouping                (Software Engineering, Finance)
  role   → selectable leaf job title         (Frontend Developer, Accountant)

Run after the migration `a1b2c3d4e5f6_roles_type_and_i18n.py`.
Safe to re-run — uses get_or_create so duplicates are skipped.
"""
import uuid
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.career.role import Role
from app.models.career.skill import Skill
from app.models.career.role_skill import RoleSkill


# ─────────────────────────────────────────────────────────────────────────────
#  ROLE TREE
#  Three-level structure:
#    field → { domains → { roles → description } }
#
#  Each entry carries name_en (= name) and name_ar for i18n.
# ─────────────────────────────────────────────────────────────────────────────

ROLE_TREE: list[dict] = [

    # ═══════════════════════════════════════════════════════════════════════
    #  FIELD: Information Technology
    # ═══════════════════════════════════════════════════════════════════════
    {
        "name_en": "Information Technology",
        "name_ar": "تقنية المعلومات",
        "role_type": "field",
        "description": "Software, data, cybersecurity, and cloud disciplines.",
        "domains": [
            {
                "name_en": "Software Engineering",
                "name_ar": "هندسة البرمجيات",
                "description": "Design, develop, and maintain software systems and applications.",
                "roles": [
                    {"name_en": "Backend Developer",    "name_ar": "مطور خلفي",           "description": "Build server-side logic, APIs, and database integrations."},
                    {"name_en": "Frontend Developer",   "name_ar": "مطور واجهات",          "description": "Create user interfaces and client-side web applications."},
                    {"name_en": "Full-Stack Developer", "name_ar": "مطور متكامل",          "description": "Work across both frontend and backend of applications."},
                    {"name_en": "Mobile App Developer", "name_ar": "مطور تطبيقات جوالة",   "description": "Build native or cross-platform mobile applications."},
                    {"name_en": "DevOps Engineer",      "name_ar": "مهندس ديف أوبس",       "description": "Manage CI/CD pipelines, infrastructure, and deployment."},
                    {"name_en": "QA / Test Engineer",   "name_ar": "مهندس جودة واختبار",   "description": "Design and execute testing strategies for software quality."},
                ],
            },
            {
                "name_en": "Data & AI",
                "name_ar": "البيانات والذكاء الاصطناعي",
                "description": "Extract insights from data and build intelligent systems.",
                "roles": [
                    {"name_en": "Data Analyst",               "name_ar": "محلل بيانات",                     "description": "Analyze datasets to produce actionable business insights."},
                    {"name_en": "Data Engineer",              "name_ar": "مهندس بيانات",                    "description": "Build and maintain data pipelines and warehousing systems."},
                    {"name_en": "Data Scientist",             "name_ar": "عالم بيانات",                     "description": "Apply statistics and machine learning to solve complex problems."},
                    {"name_en": "Machine Learning Engineer",  "name_ar": "مهندس تعلم آلي",                  "description": "Develop, train, and deploy ML models in production."},
                    {"name_en": "AI Research Engineer",       "name_ar": "مهندس أبحاث ذكاء اصطناعي",       "description": "Conduct research on new AI techniques and architectures."},
                ],
            },
            {
                "name_en": "Cybersecurity",
                "name_ar": "الأمن السيبراني",
                "description": "Protect systems, networks, and data from digital threats.",
                "roles": [
                    {"name_en": "Security Analyst",    "name_ar": "محلل أمن",                       "description": "Monitor systems for vulnerabilities and respond to incidents."},
                    {"name_en": "Penetration Tester",  "name_ar": "مختبر اختراق",                   "description": "Simulate attacks to identify security weaknesses."},
                    {"name_en": "Security Engineer",   "name_ar": "مهندس أمن",                      "description": "Design and implement security controls and architectures."},
                    {"name_en": "GRC Specialist",      "name_ar": "متخصص حوكمة ومخاطر وامتثال",     "description": "Manage governance, risk, and compliance frameworks."},
                    {"name_en": "VAPT Specialist",     "name_ar": "متخصص اختبار ثغرات واختراق",    "description": "Run vulnerability assessments and penetration tests across systems and applications."},
                    {"name_en": "SOC Analyst L1",      "name_ar": "محلل SOC المستوى 1",             "description": "Tier-1 SOC monitoring, triage, and initial incident classification."},
                    {"name_en": "SOC Analyst L2",      "name_ar": "محلل SOC المستوى 2",             "description": "Tier-2 SOC investigation, deeper analysis, and escalation handling."},
                    {"name_en": "SOC Analyst L3",      "name_ar": "محلل SOC المستوى 3",             "description": "Tier-3 SOC advanced threat hunting and complex incident response."},
                    {"name_en": "SOC Manager",         "name_ar": "مدير مركز العمليات الأمنية",     "description": "Lead SOC operations, processes, staffing, and stakeholder reporting."},
                    {"name_en": "Incident Responder",  "name_ar": "مستجيب حوادث أمنية",             "description": "Contain, eradicate, and recover from security incidents and breaches."},
                ],
            },
            {
                "name_en": "Networking & Cloud",
                "name_ar": "الشبكات والحوسبة السحابية",
                "description": "Design and manage network infrastructure and cloud platforms.",
                "roles": [
                    {"name_en": "Network Engineer",      "name_ar": "مهندس شبكات",          "description": "Configure and maintain enterprise network infrastructure."},
                    {"name_en": "Cloud Engineer",        "name_ar": "مهندس حوسبة سحابية",   "description": "Design and manage cloud-based systems and services."},
                    {"name_en": "Systems Administrator", "name_ar": "مدير أنظمة",            "description": "Manage servers, operating systems, and IT infrastructure."},
                ],
            },
            {
                "name_en": "Information Systems & Business",
                "name_ar": "نظم المعلومات والأعمال",
                "description": "Bridge technology and business through systems analysis and management.",
                "roles": [
                    {"name_en": "Business Analyst",    "name_ar": "محلل أعمال",        "description": "Gather requirements and translate business needs to technical specs."},
                    {"name_en": "ERP Consultant",      "name_ar": "مستشار ERP",        "description": "Implement and customize enterprise resource planning systems."},
                    {"name_en": "IT Project Manager",  "name_ar": "مدير مشاريع تقنية", "description": "Plan, execute, and deliver technology projects on time."},
                    {"name_en": "Product Manager",     "name_ar": "مدير منتج",         "description": "Define product vision, strategy, and roadmap."},
                    {"name_en": "IT Auditor",          "name_ar": "مدقق تقنية المعلومات", "description": "Assess IT governance, controls, and compliance."},
                ],
            },
            {
                "name_en": "UX & Design",
                "name_ar": "تجربة المستخدم والتصميم",
                "description": "Design user experiences and visual interfaces for digital products.",
                "roles": [
                    {"name_en": "UI/UX Designer", "name_ar": "مصمم واجهات وتجربة مستخدم", "description": "Design intuitive and visually appealing user interfaces."},
                    {"name_en": "UX Researcher",  "name_ar": "باحث تجربة مستخدم",         "description": "Conduct user research to inform design decisions."},
                ],
            },
        ],
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  FIELD: Engineering
    # ═══════════════════════════════════════════════════════════════════════
    {
        "name_en": "Engineering",
        "name_ar": "الهندسة",
        "role_type": "field",
        "description": "Physical systems design, infrastructure, and industrial engineering.",
        "domains": [
            {
                "name_en": "Industrial Engineering",
                "name_ar": "الهندسة الصناعية",
                "description": "Optimize complex processes, systems, and operations across industries.",
                "roles": [
                    {"name_en": "Industrial Engineer",          "name_ar": "مهندس صناعي",           "description": "Design and improve integrated systems of people, machines, materials, and energy."},
                    {"name_en": "Operations Research Analyst",  "name_ar": "محلل بحوث العمليات",    "description": "Use mathematical modeling to optimize decisions and processes."},
                    {"name_en": "Quality Engineer",             "name_ar": "مهندس جودة",             "description": "Develop and maintain quality assurance processes and standards."},
                ],
            },
            {
                "name_en": "Petroleum Engineering",
                "name_ar": "هندسة البترول",
                "description": "Develop methods to extract oil and gas from underground reservoirs.",
                "roles": [
                    {"name_en": "Petroleum Engineer",  "name_ar": "مهندس بترول",  "description": "Evaluate and develop strategies for extracting petroleum resources."},
                    {"name_en": "Reservoir Engineer",  "name_ar": "مهندس خزانات", "description": "Analyze subsurface reservoirs to optimize oil and gas recovery."},
                    {"name_en": "Drilling Engineer",   "name_ar": "مهندس حفر",    "description": "Plan and supervise the drilling of oil and gas wells."},
                ],
            },
            {
                "name_en": "Chemical Engineering",
                "name_ar": "الهندسة الكيميائية",
                "description": "Design processes that convert raw materials into valuable products.",
                "roles": [
                    {"name_en": "Chemical Engineer",  "name_ar": "مهندس كيميائي", "description": "Design and operate large-scale chemical manufacturing processes."},
                    {"name_en": "Process Engineer",   "name_ar": "مهندس عمليات",  "description": "Develop and optimize chemical and manufacturing process flows."},
                    {"name_en": "Materials Engineer", "name_ar": "مهندس مواد",    "description": "Develop and test materials used to create products and components."},
                ],
            },
            {
                "name_en": "Mechanical Engineering",
                "name_ar": "الهندسة الميكانيكية",
                "description": "Design and build mechanical systems, machines, and thermal devices.",
                "roles": [
                    {"name_en": "Mechanical Engineer",   "name_ar": "مهندس ميكانيكي", "description": "Design, analyze, and build mechanical and thermal systems."},
                    {"name_en": "Manufacturing Engineer","name_ar": "مهندس تصنيع",    "description": "Design and improve manufacturing processes and production systems."},
                    {"name_en": "Design Engineer",       "name_ar": "مهندس تصميم",    "description": "Create technical drawings and 3D models for mechanical components."},
                ],
            },
            {
                "name_en": "Civil Engineering",
                "name_ar": "الهندسة المدنية",
                "description": "Design and build infrastructure: roads, bridges, buildings, and water systems.",
                "roles": [
                    {"name_en": "Civil Engineer",        "name_ar": "مهندس مدني",    "description": "Plan, design, and oversee construction of infrastructure projects."},
                    {"name_en": "Structural Engineer",   "name_ar": "مهندس إنشائي", "description": "Analyze and design load-bearing structures such as bridges and buildings."},
                    {"name_en": "Construction Manager",  "name_ar": "مدير إنشاءات", "description": "Oversee construction projects from planning to completion."},
                ],
            },
        ],
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  FIELD: Business
    # ═══════════════════════════════════════════════════════════════════════
    {
        "name_en": "Business",
        "name_ar": "الأعمال",
        "role_type": "field",
        "description": "Business management, finance, accounting, and economics.",
        "domains": [
            {
                "name_en": "Business Administration",
                "name_ar": "إدارة الأعمال",
                "description": "Manage organizations and oversee day-to-day operations and strategy.",
                "roles": [
                    {"name_en": "Operations Manager",    "name_ar": "مدير عمليات",  "description": "Plan and coordinate the operations of an organization or department."},
                    {"name_en": "General Manager",       "name_ar": "مدير عام",     "description": "Oversee overall business functions, staff, and performance targets."},
                    {"name_en": "Administrative Manager","name_ar": "مدير إداري",   "description": "Lead and manage business administration, teams, and organizational strategy."},
                ],
            },
            {
                "name_en": "Accounting",
                "name_ar": "المحاسبة",
                "description": "Track, analyze, audit, and report financial information for organizations.",
                "roles": [
                    {"name_en": "Accountant",         "name_ar": "محاسب",       "description": "Record, classify, and summarize financial transactions and data."},
                    {"name_en": "Financial Auditor",  "name_ar": "مدقق مالي",   "description": "Examine financial records and ensure accuracy and compliance."},
                    {"name_en": "Tax Specialist",     "name_ar": "متخصص ضرائب", "description": "Prepare and plan tax filings for individuals and organizations."},
                ],
            },
            {
                "name_en": "Finance",
                "name_ar": "المالية",
                "description": "Manage capital, investments, valuation, and financial planning.",
                "roles": [
                    {"name_en": "Finance Officer",    "name_ar": "مسؤول مالي",     "description": "Manage financial resources, investments, and corporate budgets."},
                    {"name_en": "Financial Analyst",  "name_ar": "محلل مالي",      "description": "Analyze financial data and market trends to guide investment decisions."},
                    {"name_en": "Investment Analyst", "name_ar": "محلل استثمار",   "description": "Evaluate investment opportunities and portfolio performance."},
                ],
            },
            {
                "name_en": "Economics",
                "name_ar": "الاقتصاد",
                "description": "Study how resources are produced, distributed, and consumed at scale.",
                "roles": [
                    {"name_en": "Economist",         "name_ar": "خبير اقتصادي",  "description": "Apply economic theory to analyze markets, policy, and resource allocation."},
                    {"name_en": "Economic Analyst",  "name_ar": "محلل اقتصادي",  "description": "Research and interpret economic data to advise organizations and policy makers."},
                    {"name_en": "Policy Analyst",    "name_ar": "محلل سياسات",   "description": "Evaluate public policies and their economic and social impact."},
                ],
            },
            {
                "name_en": "Management Information Systems",
                "name_ar": "نظم المعلومات الإدارية",
                "description": "Bridge business strategy and IT through systems analysis and design.",
                "roles": [
                    {"name_en": "MIS Specialist",      "name_ar": "متخصص نظم المعلومات الإدارية", "description": "Design and manage information systems that support business decisions."},
                    {"name_en": "Systems Analyst",     "name_ar": "محلل أنظمة",                  "description": "Analyze and design information systems to meet organizational needs."},
                    {"name_en": "IT Business Analyst", "name_ar": "محلل أعمال تقنية",            "description": "Bridge the gap between IT capabilities and business requirements."},
                ],
            },
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
#  SKILLS CATALOG
# ─────────────────────────────────────────────────────────────────────────────

SKILLS_CATALOG: dict[str, list[str]] = {
    # ── IT ────────────────────────────────────────────────────────────────────
    "Programming Languages": [
        "Python", "JavaScript", "TypeScript", "Java", "C#", "C++",
        "Go", "Kotlin", "Swift", "Dart", "PHP", "Ruby", "Rust", "SQL",
    ],
    "Frameworks & Libraries": [
        "React", "Angular", "Vue.js", "Next.js", "Django", "Flask",
        "FastAPI", "Spring Boot", "Express.js", "Flutter", "React Native",
        ".NET", "Laravel", "Node.js",
    ],
    "Databases": [
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "Firebase",
        "SQL Server", "Oracle DB", "SQLite", "Supabase",
    ],
    "Cloud & DevOps": [
        "AWS", "Azure", "Google Cloud", "Docker", "Kubernetes",
        "Terraform", "CI/CD", "Linux Administration", "Git",
        "Jenkins", "GitHub Actions",
    ],
    "Data & AI": [
        "Machine Learning", "Deep Learning", "NLP",
        "Computer Vision", "TensorFlow", "PyTorch", "Pandas",
        "Data Visualization", "Power BI", "Tableau",
        "Apache Spark", "ETL Pipelines", "Statistics",
    ],
    "Cybersecurity": [
        "Network Security", "Penetration Testing", "SIEM",
        "Incident Response", "Vulnerability Assessment",
        "Cryptography", "ISO 27001", "NIST Framework",
        "Cloud Security", "Identity & Access Management",
    ],
    "Networking": [
        "TCP/IP", "DNS", "VPN", "Firewall Configuration",
        "Cisco Networking", "Load Balancing", "CCNA",
        "Wireless Networking", "Network Monitoring",
    ],
    "Design": [
        "Figma", "Adobe XD", "Sketch", "User Research",
        "Wireframing", "Prototyping", "Design Systems",
        "Usability Testing", "Accessibility (WCAG)",
    ],
    # ── Engineering ───────────────────────────────────────────────────────────
    "Engineering Software": [
        "AutoCAD", "SolidWorks", "ANSYS", "MATLAB", "Revit",
        "SAP2000", "ETABS", "CATIA", "Inventor", "Civil 3D",
    ],
    "Engineering Methods": [
        "Finite Element Analysis", "Thermodynamics", "Fluid Mechanics",
        "Structural Analysis", "Lean Manufacturing", "Six Sigma",
        "Quality Management (ISO 9001)", "Project Scheduling (Primavera / MS Project)",
        "HAZOP", "Process Simulation (Aspen HYSYS)",
        "Drilling Engineering", "Reservoir Simulation",
        "Operations Research", "Supply Chain Management",
    ],
    # ── Business ──────────────────────────────────────────────────────────────
    "Business & Management": [
        "Requirements Analysis", "Agile / Scrum", "ITIL",
        "Project Management", "Stakeholder Management",
        "Business Process Modeling", "SAP", "ERP Systems",
        "Risk Assessment", "Strategic Planning",
    ],
    "Finance & Accounting Tools": [
        "Microsoft Excel (Advanced)", "Power BI", "Tableau",
        "QuickBooks", "Xero", "SAP FI/CO", "Oracle Financials",
        "Bloomberg Terminal", "Financial Modeling",
        "IFRS / GAAP", "Zakat & Tax (ZATCA)",
    ],
    "Economics & Research": [
        "Econometrics", "Stata", "R", "SPSS",
        "Policy Analysis", "Macroeconomic Modeling",
        "Market Research", "Cost-Benefit Analysis",
    ],
    # ── Shared / Soft ─────────────────────────────────────────────────────────
    "Soft Skills": [
        "Communication", "Teamwork", "Problem Solving",
        "Critical Thinking", "Leadership", "Time Management",
        "Presentation Skills", "Adaptability",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
#  ROLE → SKILLS MAPPING
#  (role name_en → [(skill_name, importance 0.0–1.0)])
# ─────────────────────────────────────────────────────────────────────────────

ROLE_SKILLS_MAP: dict[str, list[tuple[str, float]]] = {

    # ── Software Engineering ──────────────────────────────────────────────────
    "Backend Developer": [
        ("Python", 0.9), ("FastAPI", 0.8), ("Django", 0.7), ("PostgreSQL", 0.9),
        ("Docker", 0.7), ("Git", 0.8), ("SQL", 0.9), ("Linux Administration", 0.6),
        ("CI/CD", 0.6), ("Redis", 0.5), ("Node.js", 0.5),
    ],
    "Frontend Developer": [
        ("JavaScript", 0.9), ("TypeScript", 0.8), ("React", 0.9), ("Vue.js", 0.6),
        ("Git", 0.8), ("Figma", 0.5), ("Next.js", 0.6),
    ],
    "Full-Stack Developer": [
        ("JavaScript", 0.9), ("Python", 0.7), ("React", 0.8), ("Node.js", 0.8),
        ("PostgreSQL", 0.8), ("Git", 0.8), ("Docker", 0.6), ("TypeScript", 0.7),
    ],
    "Mobile App Developer": [
        ("Flutter", 0.9), ("Dart", 0.9), ("React Native", 0.6), ("Kotlin", 0.5),
        ("Swift", 0.5), ("Firebase", 0.7), ("Git", 0.7), ("Figma", 0.5),
    ],
    "DevOps Engineer": [
        ("Docker", 0.9), ("Kubernetes", 0.9), ("AWS", 0.8), ("CI/CD", 0.9),
        ("Linux Administration", 0.9), ("Terraform", 0.8), ("Git", 0.8),
        ("Python", 0.6), ("Jenkins", 0.6), ("GitHub Actions", 0.7),
    ],
    "QA / Test Engineer": [
        ("Python", 0.6), ("Git", 0.7), ("CI/CD", 0.6), ("SQL", 0.5),
        ("Agile / Scrum", 0.7), ("Communication", 0.7),
    ],

    # ── Data & AI ─────────────────────────────────────────────────────────────
    "Data Analyst": [
        ("SQL", 0.9), ("Python", 0.8), ("Pandas", 0.8), ("Power BI", 0.8),
        ("Tableau", 0.7), ("Data Visualization", 0.9), ("Statistics", 0.8),
    ],
    "Data Engineer": [
        ("Python", 0.9), ("SQL", 0.9), ("Apache Spark", 0.8), ("ETL Pipelines", 0.9),
        ("AWS", 0.7), ("PostgreSQL", 0.7), ("Docker", 0.6),
    ],
    "Data Scientist": [
        ("Python", 0.9), ("Machine Learning", 0.9), ("Statistics", 0.9),
        ("Pandas", 0.8), ("TensorFlow", 0.7), ("PyTorch", 0.7),
        ("Data Visualization", 0.7), ("SQL", 0.7),
    ],
    "Machine Learning Engineer": [
        ("Python", 0.9), ("TensorFlow", 0.9), ("PyTorch", 0.9),
        ("Deep Learning", 0.9), ("Docker", 0.7), ("Machine Learning", 0.9),
        ("AWS", 0.6), ("CI/CD", 0.5),
    ],
    "AI Research Engineer": [
        ("Python", 0.9), ("PyTorch", 0.9), ("Deep Learning", 0.9),
        ("NLP", 0.8), ("Computer Vision", 0.8), ("Machine Learning", 0.9),
        ("Statistics", 0.8),
    ],

    # ── Cybersecurity ─────────────────────────────────────────────────────────
    "Security Analyst": [
        ("Network Security", 0.9), ("SIEM", 0.9), ("Incident Response", 0.8),
        ("Vulnerability Assessment", 0.8), ("Linux Administration", 0.6),
    ],
    "Penetration Tester": [
        ("Penetration Testing", 0.9), ("Network Security", 0.8),
        ("Python", 0.7), ("Vulnerability Assessment", 0.8),
        ("Linux Administration", 0.7), ("Cryptography", 0.6),
    ],
    "Security Engineer": [
        ("Network Security", 0.9), ("Cloud Security", 0.8), ("Cryptography", 0.7),
        ("Identity & Access Management", 0.8), ("ISO 27001", 0.7),
        ("Linux Administration", 0.7),
    ],
    "GRC Specialist": [
        ("ISO 27001", 0.9), ("NIST Framework", 0.9), ("Risk Assessment", 0.8),
        ("Stakeholder Management", 0.7), ("Communication", 0.7),
    ],
    "VAPT Specialist": [
        ("Penetration Testing", 0.9), ("Vulnerability Assessment", 0.9),
        ("Network Security", 0.7), ("Linux Administration", 0.6),
    ],
    "SOC Analyst L1": [
        ("SIEM", 0.9), ("Incident Response", 0.7), ("Network Security", 0.7),
        ("Linux Administration", 0.6),
    ],
    "SOC Analyst L2": [
        ("SIEM", 0.9), ("Incident Response", 0.9), ("Network Security", 0.8),
        ("Penetration Testing", 0.5),
    ],
    "SOC Analyst L3": [
        ("SIEM", 0.9), ("Incident Response", 0.9), ("Penetration Testing", 0.7),
        ("Vulnerability Assessment", 0.8),
    ],
    "SOC Manager": [
        ("Incident Response", 0.8), ("SIEM", 0.7), ("Agile / Scrum", 0.6),
        ("Leadership", 0.9), ("Communication", 0.9),
    ],
    "Incident Responder": [
        ("Incident Response", 0.9), ("SIEM", 0.8), ("Network Security", 0.8),
        ("Linux Administration", 0.7),
    ],

    # ── Networking & Cloud ────────────────────────────────────────────────────
    "Network Engineer": [
        ("TCP/IP", 0.9), ("Cisco Networking", 0.9), ("Firewall Configuration", 0.8),
        ("DNS", 0.8), ("VPN", 0.7), ("CCNA", 0.8), ("Network Monitoring", 0.7),
    ],
    "Cloud Engineer": [
        ("AWS", 0.9), ("Azure", 0.8), ("Google Cloud", 0.7), ("Docker", 0.8),
        ("Kubernetes", 0.8), ("Terraform", 0.8), ("Linux Administration", 0.7),
    ],
    "Systems Administrator": [
        ("Linux Administration", 0.9), ("Network Monitoring", 0.7),
        ("DNS", 0.6), ("Docker", 0.5), ("Firewall Configuration", 0.6),
    ],

    # ── Information Systems & Business ────────────────────────────────────────
    "Business Analyst": [
        ("Requirements Analysis", 0.9), ("Business Process Modeling", 0.8),
        ("SQL", 0.6), ("Stakeholder Management", 0.8), ("Agile / Scrum", 0.7),
        ("Communication", 0.8), ("Power BI", 0.6),
    ],
    "ERP Consultant": [
        ("SAP", 0.9), ("ERP Systems", 0.9), ("Business Process Modeling", 0.8),
        ("Requirements Analysis", 0.7), ("SQL", 0.6),
    ],
    "IT Project Manager": [
        ("Project Management", 0.9), ("Agile / Scrum", 0.9),
        ("Stakeholder Management", 0.8), ("Risk Assessment", 0.7),
        ("Communication", 0.8), ("Leadership", 0.8),
    ],
    "Product Manager": [
        ("Strategic Planning", 0.8), ("Requirements Analysis", 0.8),
        ("Stakeholder Management", 0.8), ("Agile / Scrum", 0.8),
        ("Communication", 0.8), ("User Research", 0.7),
    ],
    "IT Auditor": [
        ("ISO 27001", 0.9), ("ITIL", 0.8), ("Risk Assessment", 0.9),
        ("SQL", 0.5), ("Communication", 0.7),
    ],

    # ── UX & Design ───────────────────────────────────────────────────────────
    "UI/UX Designer": [
        ("Figma", 0.9), ("Wireframing", 0.9), ("Prototyping", 0.8),
        ("User Research", 0.8), ("Design Systems", 0.8),
        ("Usability Testing", 0.7), ("Accessibility (WCAG)", 0.6),
    ],
    "UX Researcher": [
        ("User Research", 0.9), ("Usability Testing", 0.9),
        ("Communication", 0.8), ("Presentation Skills", 0.7),
        ("Wireframing", 0.5),
    ],

    # ── Industrial Engineering ────────────────────────────────────────────────
    "Industrial Engineer": [
        ("Lean Manufacturing", 0.9), ("Six Sigma", 0.8),
        ("MATLAB", 0.6), ("Operations Research", 0.8),
        ("Supply Chain Management", 0.7), ("Microsoft Excel (Advanced)", 0.7),
        ("Quality Management (ISO 9001)", 0.7), ("Problem Solving", 0.8),
    ],
    "Operations Research Analyst": [
        ("Operations Research", 0.9), ("MATLAB", 0.8), ("Python", 0.7),
        ("Statistics", 0.8), ("Microsoft Excel (Advanced)", 0.8),
        ("Supply Chain Management", 0.7), ("Critical Thinking", 0.8),
    ],
    "Quality Engineer": [
        ("Quality Management (ISO 9001)", 0.9), ("Six Sigma", 0.9),
        ("MATLAB", 0.5), ("Statistics", 0.7), ("Problem Solving", 0.8),
        ("Communication", 0.7),
    ],

    # ── Petroleum Engineering ─────────────────────────────────────────────────
    "Petroleum Engineer": [
        ("Reservoir Simulation", 0.9), ("Drilling Engineering", 0.8),
        ("MATLAB", 0.6), ("Microsoft Excel (Advanced)", 0.7),
        ("Problem Solving", 0.8), ("Teamwork", 0.7),
    ],
    "Reservoir Engineer": [
        ("Reservoir Simulation", 0.9), ("MATLAB", 0.7),
        ("Statistics", 0.7), ("Microsoft Excel (Advanced)", 0.8),
        ("Critical Thinking", 0.8),
    ],
    "Drilling Engineer": [
        ("Drilling Engineering", 0.9), ("HAZOP", 0.7),
        ("Microsoft Excel (Advanced)", 0.7), ("Problem Solving", 0.8),
        ("Teamwork", 0.7),
    ],

    # ── Chemical Engineering ──────────────────────────────────────────────────
    "Chemical Engineer": [
        ("Process Simulation (Aspen HYSYS)", 0.9), ("MATLAB", 0.7),
        ("HAZOP", 0.8), ("Thermodynamics", 0.9), ("Fluid Mechanics", 0.8),
        ("Microsoft Excel (Advanced)", 0.7), ("Problem Solving", 0.8),
    ],
    "Process Engineer": [
        ("Process Simulation (Aspen HYSYS)", 0.9), ("HAZOP", 0.8),
        ("Lean Manufacturing", 0.7), ("Fluid Mechanics", 0.7),
        ("Microsoft Excel (Advanced)", 0.7),
    ],
    "Materials Engineer": [
        ("Finite Element Analysis", 0.7), ("ANSYS", 0.7), ("MATLAB", 0.6),
        ("Quality Management (ISO 9001)", 0.7), ("Problem Solving", 0.8),
        ("Critical Thinking", 0.7),
    ],

    # ── Mechanical Engineering ────────────────────────────────────────────────
    "Mechanical Engineer": [
        ("SolidWorks", 0.8), ("AutoCAD", 0.8), ("ANSYS", 0.7),
        ("MATLAB", 0.7), ("Thermodynamics", 0.8), ("Finite Element Analysis", 0.7),
        ("Microsoft Excel (Advanced)", 0.6), ("Problem Solving", 0.8),
    ],
    "Manufacturing Engineer": [
        ("AutoCAD", 0.8), ("SolidWorks", 0.7), ("Lean Manufacturing", 0.9),
        ("Six Sigma", 0.8), ("Quality Management (ISO 9001)", 0.8),
        ("Microsoft Excel (Advanced)", 0.7),
    ],
    "Design Engineer": [
        ("SolidWorks", 0.9), ("CATIA", 0.7), ("Inventor", 0.7),
        ("AutoCAD", 0.8), ("Finite Element Analysis", 0.6),
        ("ANSYS", 0.6), ("Problem Solving", 0.8),
    ],

    # ── Civil Engineering ─────────────────────────────────────────────────────
    "Civil Engineer": [
        ("AutoCAD", 0.9), ("Civil 3D", 0.8), ("Revit", 0.7),
        ("Structural Analysis", 0.8), ("Microsoft Excel (Advanced)", 0.7),
        ("Project Scheduling (Primavera / MS Project)", 0.7), ("Problem Solving", 0.8),
    ],
    "Structural Engineer": [
        ("SAP2000", 0.9), ("ETABS", 0.9), ("AutoCAD", 0.8),
        ("Structural Analysis", 0.9), ("Finite Element Analysis", 0.8),
        ("Revit", 0.7), ("Critical Thinking", 0.8),
    ],
    "Construction Manager": [
        ("Project Scheduling (Primavera / MS Project)", 0.9),
        ("AutoCAD", 0.6), ("Leadership", 0.9), ("Stakeholder Management", 0.8),
        ("Risk Assessment", 0.7), ("Communication", 0.8),
        ("Microsoft Excel (Advanced)", 0.7),
    ],

    # ── Business Administration ───────────────────────────────────────────────
    "Operations Manager": [
        ("Strategic Planning", 0.9), ("Leadership", 0.9),
        ("Stakeholder Management", 0.8), ("Microsoft Excel (Advanced)", 0.7),
        ("ERP Systems", 0.6), ("Communication", 0.8), ("Problem Solving", 0.8),
    ],
    "General Manager": [
        ("Strategic Planning", 0.9), ("Leadership", 0.9),
        ("Stakeholder Management", 0.9), ("Communication", 0.9),
        ("Risk Assessment", 0.7), ("Presentation Skills", 0.8),
    ],
    "Administrative Manager": [
        ("Leadership", 0.8), ("Communication", 0.9), ("Teamwork", 0.8),
        ("Microsoft Excel (Advanced)", 0.7), ("Time Management", 0.8),
        ("Stakeholder Management", 0.7),
    ],

    # ── Accounting ────────────────────────────────────────────────────────────
    "Accountant": [
        ("Microsoft Excel (Advanced)", 0.9), ("QuickBooks", 0.8), ("Xero", 0.7),
        ("IFRS / GAAP", 0.9), ("SAP FI/CO", 0.6), ("Zakat & Tax (ZATCA)", 0.7),
        ("Critical Thinking", 0.7), ("Communication", 0.6),
    ],
    "Financial Auditor": [
        ("IFRS / GAAP", 0.9), ("Microsoft Excel (Advanced)", 0.8),
        ("SAP FI/CO", 0.6), ("Risk Assessment", 0.8), ("Critical Thinking", 0.9),
        ("Communication", 0.7),
    ],
    "Tax Specialist": [
        ("Zakat & Tax (ZATCA)", 0.9), ("IFRS / GAAP", 0.8),
        ("Microsoft Excel (Advanced)", 0.8), ("SAP FI/CO", 0.5),
        ("Communication", 0.7), ("Critical Thinking", 0.8),
    ],

    # ── Finance ───────────────────────────────────────────────────────────────
    "Finance Officer": [
        ("Financial Modeling", 0.9), ("Microsoft Excel (Advanced)", 0.9),
        ("SAP FI/CO", 0.7), ("Oracle Financials", 0.6), ("IFRS / GAAP", 0.8),
        ("Power BI", 0.6), ("Critical Thinking", 0.7),
    ],
    "Financial Analyst": [
        ("Financial Modeling", 0.9), ("Microsoft Excel (Advanced)", 0.9),
        ("Bloomberg Terminal", 0.7), ("Power BI", 0.7), ("Tableau", 0.6),
        ("Statistics", 0.7), ("Critical Thinking", 0.8),
    ],
    "Investment Analyst": [
        ("Financial Modeling", 0.9), ("Bloomberg Terminal", 0.9),
        ("Microsoft Excel (Advanced)", 0.9), ("Statistics", 0.7),
        ("Critical Thinking", 0.9), ("Presentation Skills", 0.7),
    ],

    # ── Economics ─────────────────────────────────────────────────────────────
    "Economist": [
        ("Econometrics", 0.9), ("Stata", 0.8), ("R", 0.7), ("SPSS", 0.6),
        ("Macroeconomic Modeling", 0.9), ("Policy Analysis", 0.8),
        ("Statistics", 0.9), ("Critical Thinking", 0.9),
    ],
    "Economic Analyst": [
        ("Econometrics", 0.8), ("Stata", 0.7), ("Microsoft Excel (Advanced)", 0.8),
        ("Market Research", 0.8), ("Statistics", 0.8),
        ("Cost-Benefit Analysis", 0.8), ("Presentation Skills", 0.7),
    ],
    "Policy Analyst": [
        ("Policy Analysis", 0.9), ("Market Research", 0.8),
        ("Cost-Benefit Analysis", 0.8), ("Statistics", 0.7),
        ("Communication", 0.8), ("Presentation Skills", 0.8),
        ("Critical Thinking", 0.9),
    ],

    # ── Management Information Systems ────────────────────────────────────────
    "MIS Specialist": [
        ("ERP Systems", 0.9), ("SAP", 0.8), ("Business Process Modeling", 0.8),
        ("SQL", 0.7), ("Power BI", 0.7), ("Requirements Analysis", 0.7),
        ("Strategic Planning", 0.6),
    ],
    "Systems Analyst": [
        ("Requirements Analysis", 0.9), ("Business Process Modeling", 0.9),
        ("SQL", 0.7), ("Stakeholder Management", 0.8), ("Communication", 0.8),
        ("Microsoft Excel (Advanced)", 0.6),
    ],
    "IT Business Analyst": [
        ("Requirements Analysis", 0.9), ("Agile / Scrum", 0.8),
        ("Business Process Modeling", 0.8), ("SQL", 0.6),
        ("Stakeholder Management", 0.8), ("Communication", 0.8),
        ("Power BI", 0.6),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_or_create(db: Session, model, defaults=None, **kwargs):
    """Fetch an existing row or insert a new one. Returns (instance, created)."""
    instance = db.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    params = {**kwargs, **(defaults or {})}
    instance = model(**params)
    db.add(instance)
    db.flush()
    return instance, True


# ─────────────────────────────────────────────────────────────────────────────
#  SEED FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def seed(db: Session | None = None) -> None:
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        # ── 1. Roles (3-level tree) ───────────────────────────────────────────
        print("Seeding roles…")
        role_map: dict[str, Role] = {}   # name_en → Role

        for field_data in ROLE_TREE:
            # ── Field (root) ──────────────────────────────────────────────────
            field_name = field_data["name_en"]
            field, created = get_or_create(
                db, Role,
                name=field_name,
                defaults={
                    "name_en":    field_name,
                    "name_ar":    field_data["name_ar"],
                    "description": field_data["description"],
                    "role_type":  "field",
                    "parent_id":  None,
                },
            )
            # Update name_ar if row already existed (idempotent fix)
            if not created and field.name_ar == field.name:
                field.name_ar = field_data["name_ar"]
                field.name_en = field_name
            role_map[field_name] = field
            print(f"  [{'CREATED' if created else 'exists '}] FIELD: {field_name}")

            for domain_data in field_data["domains"]:
                # ── Domain (mid-level) ────────────────────────────────────────
                domain_name = domain_data["name_en"]
                domain, created = get_or_create(
                    db, Role,
                    name=domain_name,
                    defaults={
                        "name_en":    domain_name,
                        "name_ar":    domain_data["name_ar"],
                        "description": domain_data["description"],
                        "role_type":  "domain",
                        "parent_id":  field.id,
                    },
                )
                if not created:
                    # Idempotent: make sure role_type and parent_id are correct
                    if domain.role_type != "domain":
                        domain.role_type = "domain"
                    if domain.parent_id != field.id:
                        domain.parent_id = field.id
                    if domain.name_ar == domain.name:
                        domain.name_ar = domain_data["name_ar"]
                    if not domain.name_en:
                        domain.name_en = domain_name
                role_map[domain_name] = domain
                print(f"    [{'CREATED' if created else 'exists '}]   DOMAIN: {domain_name}")

                for role_data in domain_data["roles"]:
                    # ── Role (leaf / selectable) ──────────────────────────────
                    role_name = role_data["name_en"]
                    role, created = get_or_create(
                        db, Role,
                        name=role_name,
                        defaults={
                            "name_en":    role_name,
                            "name_ar":    role_data["name_ar"],
                            "description": role_data["description"],
                            "role_type":  "role",
                            "parent_id":  domain.id,
                        },
                    )
                    if not created:
                        if role.name_ar == role.name:
                            role.name_ar = role_data["name_ar"]
                        if not role.name_en:
                            role.name_en = role_name
                        if role.role_type != "role":
                            role.role_type = "role"
                    role_map[role_name] = role
                    print(f"      [{'CREATED' if created else 'exists '}]     ROLE: {role_name}")

        # ── 2. Skills ─────────────────────────────────────────────────────────
        print("\nSeeding skills…")
        skill_map: dict[str, Skill] = {}

        for category, skill_names in SKILLS_CATALOG.items():
            for skill_name in skill_names:
                skill, created = get_or_create(
                    db, Skill,
                    name=skill_name,
                    defaults={"category": category},
                )
                skill_map[skill_name] = skill
                if created:
                    print(f"  [CREATED] {skill_name}  ({category})")

        # ── 3. Role → skill mappings ──────────────────────────────────────────
        print("\nSeeding role-skill mappings…")
        mapping_count = 0

        for role_name, skills_list in ROLE_SKILLS_MAP.items():
            role = role_map.get(role_name)
            if not role:
                print(f"  [WARN] Role '{role_name}' not found — skipping")
                continue

            for skill_name, weight in skills_list:
                skill = skill_map.get(skill_name)
                if not skill:
                    print(f"  [WARN] Skill '{skill_name}' not found — skipping")
                    continue

                _, created = get_or_create(
                    db, RoleSkill,
                    role_id=role.id,
                    skill_id=skill.id,
                    defaults={"importance_weight": weight},
                )
                if created:
                    mapping_count += 1

        print(f"  Created {mapping_count} new role-skill mappings")

        db.commit()
        print("\n✓ Seed complete!")

    except Exception as e:
        db.rollback()
        print(f"✗ Seed failed: {e}")
        raise
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    seed()