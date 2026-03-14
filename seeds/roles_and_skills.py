"""
Seed script for roles and skills tables.

Usage:
    python -m app.seeds.roles_and_skills

This populates the roles (tree structure) and skills tables,
plus the role_skills mapping. Safe to run multiple times —
uses ON CONFLICT DO NOTHING via get_or_create pattern.
"""
import uuid
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.career.role import Role
from app.models.career.skill import Skill
from app.models.career.role_skill import RoleSkill


# ────────────────────────────────────────────
#  ROLE TREE DATA
#  Format: { "Field Name": ["Specialization 1", "Specialization 2", ...] }
# ────────────────────────────────────────────

ROLE_TREE: dict[str, dict] = {
    "Software Engineering": {
        "description": "Design, develop, and maintain software systems and applications.",
        "children": {
            "Backend Developer": "Build server-side logic, APIs, and database integrations.",
            "Frontend Developer": "Create user interfaces and client-side web applications.",
            "Full-Stack Developer": "Work across both frontend and backend of applications.",
            "Mobile App Developer": "Build native or cross-platform mobile applications.",
            "DevOps Engineer": "Manage CI/CD pipelines, infrastructure, and deployment.",
            "QA / Test Engineer": "Design and execute testing strategies for software quality.",
        },
    },
    "Data & AI": {
        "description": "Extract insights from data and build intelligent systems.",
        "children": {
            "Data Analyst": "Analyze datasets to produce actionable business insights.",
            "Data Engineer": "Build and maintain data pipelines and warehousing systems.",
            "Data Scientist": "Apply statistics and machine learning to solve complex problems.",
            "Machine Learning Engineer": "Develop, train, and deploy ML models in production.",
            "AI Research Engineer": "Conduct research on new AI techniques and architectures.",
        },
    },
    "Cybersecurity": {
        "description": "Protect systems, networks, and data from digital threats.",
        "children": {
            "Security Analyst": "Monitor systems for vulnerabilities and respond to incidents.",
            "Penetration Tester": "Simulate attacks to identify security weaknesses.",
            "Security Engineer": "Design and implement security controls and architectures.",
            "GRC Specialist": "Manage governance, risk, and compliance frameworks.",
        },
    },
    "Networking & Cloud": {
        "description": "Design and manage network infrastructure and cloud platforms.",
        "children": {
            "Network Engineer": "Configure and maintain enterprise network infrastructure.",
            "Cloud Engineer": "Design and manage cloud-based systems and services.",
            "Systems Administrator": "Manage servers, operating systems, and IT infrastructure.",
        },
    },
    "Information Systems & Business": {
        "description": "Bridge technology and business through systems analysis and management.",
        "children": {
            "Business Analyst": "Gather requirements and translate business needs to technical specs.",
            "ERP Consultant": "Implement and customize enterprise resource planning systems.",
            "IT Project Manager": "Plan, execute, and deliver technology projects on time.",
            "Product Manager": "Define product vision, strategy, and roadmap.",
            "IT Auditor": "Assess IT governance, controls, and compliance.",
        },
    },
    "UX & Design": {
        "description": "Design user experiences and visual interfaces for digital products.",
        "children": {
            "UI/UX Designer": "Design intuitive and visually appealing user interfaces.",
            "UX Researcher": "Conduct user research to inform design decisions.",
        },
    },
}


# ────────────────────────────────────────────
#  SKILLS CATALOG
#  Format: { "Category": ["Skill 1", "Skill 2", ...] }
# ────────────────────────────────────────────

SKILLS_CATALOG: dict[str, list[str]] = {
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
    "Business & Management": [
        "Requirements Analysis", "Agile / Scrum", "ITIL",
        "Project Management", "Stakeholder Management",
        "Business Process Modeling", "SAP", "ERP Systems",
        "Risk Assessment", "Strategic Planning",
    ],
    "Design": [
        "Figma", "Adobe XD", "Sketch", "User Research",
        "Wireframing", "Prototyping", "Design Systems",
        "Usability Testing", "Accessibility (WCAG)",
    ],
    "Soft Skills": [
        "Communication", "Teamwork", "Problem Solving",
        "Critical Thinking", "Leadership", "Time Management",
        "Presentation Skills", "Adaptability",
    ],
}


# ────────────────────────────────────────────
#  ROLE → SKILLS MAPPING
#  Maps child role names to skill names + importance (0.0-1.0)
# ────────────────────────────────────────────

ROLE_SKILLS_MAP: dict[str, list[tuple[str, float]]] = {
    "Backend Developer": [
        ("Python", 0.9), ("FastAPI", 0.8), ("Django", 0.7), ("PostgreSQL", 0.9),
        ("Docker", 0.7), ("Git", 0.8), ("SQL", 0.9), ("Linux Administration", 0.6),
        ("CI/CD", 0.6), ("Redis", 0.5), ("Node.js", 0.5),
    ],
    "Frontend Developer": [
        ("JavaScript", 0.9), ("TypeScript", 0.8), ("React", 0.9), ("Vue.js", 0.6),
        ("HTML/CSS", 0.9), ("Git", 0.8), ("Figma", 0.5), ("Next.js", 0.6),
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
    "Network Engineer": [
        ("TCP/IP", 0.9), ("Cisco Networking", 0.9), ("Firewall Configuration", 0.8),
        ("DNS", 0.8), ("VPN", 0.7), ("CCNA", 0.8), ("Network Monitoring", 0.7),
    ],
    "Cloud Engineer": [
        ("AWS", 0.9), ("Azure", 0.8), ("Google Cloud", 0.7), ("Docker", 0.8),
        ("Kubernetes", 0.8), ("Terraform", 0.8), ("Linux Administration", 0.7),
    ],
    "Systems Administrator": [
        ("Linux Administration", 0.9), ("Windows Server", 0.7),
        ("Network Monitoring", 0.7), ("DNS", 0.6), ("Docker", 0.5),
    ],
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
}


def get_or_create(db: Session, model, defaults=None, **kwargs):
    """Get existing record or create new one."""
    instance = db.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    params = {**kwargs, **(defaults or {})}
    instance = model(**params)
    db.add(instance)
    db.flush()
    return instance, True


def seed(db: Session | None = None):
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        print("Seeding roles...")
        role_map: dict[str, Role] = {}  # name -> Role

        for field_name, field_data in ROLE_TREE.items():
            parent, created = get_or_create(
                db, Role,
                name=field_name,
                defaults={"description": field_data["description"]},
            )
            role_map[field_name] = parent
            status = "CREATED" if created else "exists"
            print(f"  [{status}] {field_name}")

            for child_name, child_desc in field_data["children"].items():
                child, created = get_or_create(
                    db, Role,
                    name=child_name,
                    defaults={"description": child_desc, "parent_id": parent.id},
                )
                role_map[child_name] = child
                status = "CREATED" if created else "exists"
                print(f"    [{status}] {child_name}")

        print("\nSeeding skills...")
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
                    print(f"  [CREATED] {skill_name} ({category})")

        print("\nSeeding role-skill mappings...")
        mapping_count = 0

        for role_name, skills_list in ROLE_SKILLS_MAP.items():
            role = role_map.get(role_name)
            if not role:
                print(f"  [WARN] Role '{role_name}' not found, skipping")
                continue

            for skill_name, weight in skills_list:
                skill = skill_map.get(skill_name)
                if not skill:
                    print(f"  [WARN] Skill '{skill_name}' not found, skipping")
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
        print("\nSeed complete!")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    seed()