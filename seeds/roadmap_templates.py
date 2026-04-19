"""
Seed script for roadmap templates (bilingual: English + Arabic).

Usage:
    python -m seeds.roadmap_templates

Creates pre-built roadmap templates for common roles.
Safe to run multiple times — updates existing templates.
"""

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.career.role import Role
from app.models.roadmap.models import RoadmapTemplate


# ────────────────────────────────────────────────────────────
#  TEMPLATE DATA — keyed by role name (must match roles table)
#  Every title/description has a _ar counterpart.
#  Resource titles stay in English (original language).
# ────────────────────────────────────────────────────────────

TEMPLATES: dict[str, dict] = {

    # ══════════════════════════════════════════════════════════
    #  BACKEND DEVELOPER
    # ══════════════════════════════════════════════════════════
    "Backend Developer": {
        "title": "Backend Developer Roadmap",
        "title_ar": "خارطة طريق مطوّر الباك إند",
        "stages": [
            {
                "order": 1,
                "title": "Programming Foundations",
                "title_ar": "أساسيات البرمجة",
                "description": "Master a backend language and core programming concepts before building APIs.",
                "description_ar": "أتقن لغة برمجة خلفية ومفاهيم البرمجة الأساسية قبل بناء الـ APIs.",
                "tasks": [
                    {
                        "order": 1,
                        "title": "Learn Python fundamentals",
                        "title_ar": "تعلّم أساسيات بايثون",
                        "description": "Variables, data types, control flow, functions, OOP, and error handling.",
                        "description_ar": "المتغيرات، أنواع البيانات، التحكم بالتدفق، الدوال، البرمجة الكائنية، ومعالجة الأخطاء.",
                        "skill_name": "Python",
                        "resources": [
                            {"type": "course", "title": "Python for Everybody (Coursera)", "url": "https://www.coursera.org/specializations/python"},
                            {"type": "video", "title": "CS50P – Harvard Python Course", "url": "https://cs50.harvard.edu/python/"},
                        ],
                    },
                    {
                        "order": 2,
                        "title": "Learn SQL & relational databases",
                        "title_ar": "تعلّم SQL وقواعد البيانات العلائقية",
                        "description": "SELECT, JOIN, GROUP BY, indexes, and database design fundamentals.",
                        "description_ar": "استعلامات SELECT وJOIN وGROUP BY والفهارس وأساسيات تصميم قواعد البيانات.",
                        "skill_name": "SQL",
                        "resources": [
                            {"type": "course", "title": "SQL for Data Science (Coursera)", "url": "https://www.coursera.org/learn/sql-for-data-science"},
                            {"type": "article", "title": "SQLBolt – Interactive SQL Tutorials", "url": "https://sqlbolt.com/"},
                        ],
                    },
                    {
                        "order": 3,
                        "title": "Git version control",
                        "title_ar": "التحكم بالإصدارات باستخدام Git",
                        "description": "Branching, merging, pull requests, and collaborative workflows.",
                        "description_ar": "التفرع، الدمج، طلبات السحب، وسير العمل التعاوني.",
                        "skill_name": "Git",
                        "resources": [
                            {"type": "video", "title": "Git & GitHub Crash Course (freeCodeCamp)", "url": "https://www.youtube.com/watch?v=RGOj5yH7evk"},
                        ],
                    },
                ],
            },
            {
                "order": 2,
                "title": "API Development",
                "title_ar": "تطوير الـ APIs",
                "description": "Build REST APIs — the core skill of every backend developer.",
                "description_ar": "ابنِ واجهات REST API — المهارة الأساسية لكل مطوّر باك إند.",
                "tasks": [
                    {
                        "order": 1,
                        "title": "Build REST APIs with FastAPI",
                        "title_ar": "بناء REST APIs باستخدام FastAPI",
                        "description": "Routes, path/query params, request bodies, response models, dependency injection.",
                        "description_ar": "المسارات، معاملات المسار والاستعلام، أجسام الطلبات، نماذج الاستجابة، وحقن التبعيات.",
                        "skill_name": "FastAPI",
                        "resources": [
                            {"type": "article", "title": "FastAPI Official Tutorial", "url": "https://fastapi.tiangolo.com/tutorial/"},
                            {"type": "video", "title": "FastAPI Full Course (freeCodeCamp)", "url": "https://www.youtube.com/watch?v=0sOvCWFmrtA"},
                        ],
                    },
                    {
                        "order": 2,
                        "title": "Database integration with SQLAlchemy",
                        "title_ar": "ربط قواعد البيانات باستخدام SQLAlchemy",
                        "description": "ORM basics, models, sessions, relationships, and migrations with Alembic.",
                        "description_ar": "أساسيات ORM، النماذج، الجلسات، العلاقات، والترحيل باستخدام Alembic.",
                        "skill_name": "PostgreSQL",
                        "resources": [
                            {"type": "article", "title": "SQLAlchemy ORM Tutorial", "url": "https://docs.sqlalchemy.org/en/20/orm/tutorial.html"},
                        ],
                    },
                    {
                        "order": 3,
                        "title": "Authentication & authorization",
                        "title_ar": "المصادقة والتفويض",
                        "description": "JWT tokens, OAuth2, role-based access control patterns.",
                        "description_ar": "رموز JWT، بروتوكول OAuth2، وأنماط التحكم بالوصول حسب الأدوار.",
                        "skill_name": None,
                        "resources": [
                            {"type": "article", "title": "FastAPI Security Guide", "url": "https://fastapi.tiangolo.com/tutorial/security/"},
                        ],
                    },
                ],
            },
            {
                "order": 3,
                "title": "DevOps Essentials",
                "title_ar": "أساسيات DevOps",
                "description": "Learn to containerize and deploy your applications.",
                "description_ar": "تعلّم حاويات التطبيقات ونشرها.",
                "tasks": [
                    {
                        "order": 1,
                        "title": "Docker fundamentals",
                        "title_ar": "أساسيات Docker",
                        "description": "Dockerfiles, images, containers, docker-compose for local development.",
                        "description_ar": "ملفات Dockerfile، الصور، الحاويات، واستخدام docker-compose للتطوير المحلي.",
                        "skill_name": "Docker",
                        "resources": [
                            {"type": "video", "title": "Docker Tutorial for Beginners (TechWorld with Nana)", "url": "https://www.youtube.com/watch?v=3c-iBn73dDE"},
                        ],
                    },
                    {
                        "order": 2,
                        "title": "CI/CD pipelines",
                        "title_ar": "أنابيب CI/CD",
                        "description": "GitHub Actions or similar — automate testing and deployment.",
                        "description_ar": "GitHub Actions أو ما يشابهها — أتمتة الاختبار والنشر.",
                        "skill_name": "CI/CD",
                        "resources": [
                            {"type": "article", "title": "GitHub Actions Documentation", "url": "https://docs.github.com/en/actions"},
                        ],
                    },
                ],
            },
            {
                "order": 4,
                "title": "Production Readiness",
                "title_ar": "الجاهزية للإنتاج",
                "description": "Caching, monitoring, and performance — what separates juniors from mids.",
                "description_ar": "التخزين المؤقت، المراقبة، والأداء — ما يميّز المبتدئ عن المتوسط.",
                "tasks": [
                    {
                        "order": 1,
                        "title": "Caching with Redis",
                        "title_ar": "التخزين المؤقت باستخدام Redis",
                        "description": "Key-value storage, caching strategies, session management.",
                        "description_ar": "تخزين مفتاح-قيمة، استراتيجيات التخزين المؤقت، وإدارة الجلسات.",
                        "skill_name": "Redis",
                        "resources": [{"type": "article", "title": "Redis University (free courses)", "url": "https://university.redis.com/"}],
                    },
                    {
                        "order": 2,
                        "title": "Linux server basics",
                        "title_ar": "أساسيات خوادم لينكس",
                        "description": "Command line, file permissions, systemd, SSH, basic networking.",
                        "description_ar": "سطر الأوامر، صلاحيات الملفات، systemd، SSH، وأساسيات الشبكات.",
                        "skill_name": "Linux Administration",
                        "resources": [{"type": "course", "title": "Linux Command Line Basics (Udacity)", "url": "https://www.udacity.com/course/linux-command-line-basics--ud595"}],
                    },
                    {
                        "order": 3,
                        "title": "Build a capstone project",
                        "title_ar": "بناء مشروع تخرّج",
                        "description": "Build and deploy a full API project with auth, database, caching, and CI/CD.",
                        "description_ar": "ابنِ وانشر مشروع API كامل يتضمن المصادقة، قاعدة بيانات، تخزين مؤقت، و CI/CD.",
                        "skill_name": None,
                        "resources": [{"type": "article", "title": "Backend Project Ideas", "url": "https://roadmap.sh/backend/projects"}],
                    },
                ],
            },
        ],
    },

    # ══════════════════════════════════════════════════════════
    #  FRONTEND DEVELOPER
    # ══════════════════════════════════════════════════════════
    "Frontend Developer": {
        "title": "Frontend Developer Roadmap",
        "title_ar": "خارطة طريق مطوّر الواجهات الأمامية",
        "stages": [
            {
                "order": 1,
                "title": "Web Fundamentals",
                "title_ar": "أساسيات الويب",
                "description": "HTML, CSS, and JavaScript — the building blocks of every website.",
                "description_ar": "HTML وCSS وJavaScript — اللبنات الأساسية لكل موقع ويب.",
                "tasks": [
                    {"order": 1, "title": "HTML & CSS mastery", "title_ar": "إتقان HTML و CSS", "description": "Semantic HTML, Flexbox, Grid, responsive design, accessibility basics.", "description_ar": "HTML الدلالي، Flexbox، Grid، التصميم المتجاوب، وأساسيات إمكانية الوصول.", "skill_name": None, "resources": [{"type": "course", "title": "freeCodeCamp Responsive Web Design", "url": "https://www.freecodecamp.org/learn/2022/responsive-web-design/"}, {"type": "article", "title": "MDN Web Docs – HTML & CSS", "url": "https://developer.mozilla.org/en-US/docs/Learn"}]},
                    {"order": 2, "title": "JavaScript fundamentals", "title_ar": "أساسيات JavaScript", "description": "Variables, functions, DOM manipulation, events, async/await, ES6+ features.", "description_ar": "المتغيرات، الدوال، التعامل مع DOM، الأحداث، async/await، وميزات ES6+.", "skill_name": "JavaScript", "resources": [{"type": "course", "title": "JavaScript Algorithms and Data Structures (freeCodeCamp)", "url": "https://www.freecodecamp.org/learn/javascript-algorithms-and-data-structures-v8/"}]},
                    {"order": 3, "title": "Git version control", "title_ar": "التحكم بالإصدارات باستخدام Git", "description": "Branching, merging, pull requests, and collaborative workflows.", "description_ar": "التفرع، الدمج، طلبات السحب، وسير العمل التعاوني.", "skill_name": "Git", "resources": [{"type": "video", "title": "Git & GitHub Crash Course", "url": "https://www.youtube.com/watch?v=RGOj5yH7evk"}]},
                ],
            },
            {
                "order": 2,
                "title": "React & Modern Frontend",
                "title_ar": "React والواجهات الحديثة",
                "description": "Learn the most in-demand frontend framework.",
                "description_ar": "تعلّم إطار العمل الأكثر طلباً في سوق العمل.",
                "tasks": [
                    {"order": 1, "title": "React fundamentals", "title_ar": "أساسيات React", "description": "Components, props, state, hooks, event handling, and JSX.", "description_ar": "المكونات، الخصائص، الحالة، الخطافات، معالجة الأحداث، و JSX.", "skill_name": "React", "resources": [{"type": "article", "title": "React Official Tutorial", "url": "https://react.dev/learn"}]},
                    {"order": 2, "title": "TypeScript basics", "title_ar": "أساسيات TypeScript", "description": "Types, interfaces, generics — write safer, more maintainable code.", "description_ar": "الأنواع، الواجهات، الأنواع العامة — اكتب كوداً أكثر أماناً وسهولة في الصيانة.", "skill_name": "TypeScript", "resources": [{"type": "article", "title": "TypeScript Handbook", "url": "https://www.typescriptlang.org/docs/handbook/"}]},
                ],
            },
            {
                "order": 3,
                "title": "State Management & Routing",
                "title_ar": "إدارة الحالة والتوجيه",
                "description": "Build real multi-page apps with complex state.",
                "description_ar": "ابنِ تطبيقات حقيقية متعددة الصفحات مع حالة معقدة.",
                "tasks": [
                    {"order": 1, "title": "Next.js fundamentals", "title_ar": "أساسيات Next.js", "description": "File-based routing, SSR, SSG, API routes, and deployment.", "description_ar": "التوجيه المبني على الملفات، SSR، SSG، مسارات API، والنشر.", "skill_name": "Next.js", "resources": [{"type": "article", "title": "Next.js Official Learn Course", "url": "https://nextjs.org/learn"}]},
                    {"order": 2, "title": "API integration patterns", "title_ar": "أنماط التكامل مع APIs", "description": "Fetching data, loading states, error handling, React Query / SWR.", "description_ar": "جلب البيانات، حالات التحميل، معالجة الأخطاء، React Query / SWR.", "skill_name": None, "resources": [{"type": "article", "title": "TanStack Query Documentation", "url": "https://tanstack.com/query/latest"}]},
                ],
            },
            {
                "order": 4,
                "title": "Design & Portfolio",
                "title_ar": "التصميم وملف الأعمال",
                "description": "Polish your UI skills and build projects that demonstrate your abilities.",
                "description_ar": "صقل مهارات واجهة المستخدم وابنِ مشاريع تُظهر قدراتك.",
                "tasks": [
                    {"order": 1, "title": "UI/UX fundamentals for developers", "title_ar": "أساسيات UI/UX للمطورين", "description": "Spacing, typography, color theory, and component design.", "description_ar": "المسافات، الخطوط، نظرية الألوان، وتصميم المكونات.", "skill_name": "Figma", "resources": [{"type": "video", "title": "Design for Developers (Kevin Powell)", "url": "https://www.youtube.com/watch?v=0sOvCWFmrtA"}]},
                    {"order": 2, "title": "Build a portfolio website", "title_ar": "بناء موقع ملف أعمال", "description": "Create a personal portfolio showcasing 3+ projects. Deploy it live.", "description_ar": "أنشئ ملف أعمال شخصي يعرض 3 مشاريع أو أكثر. انشره على الإنترنت.", "skill_name": None, "resources": [{"type": "article", "title": "Frontend Project Ideas", "url": "https://roadmap.sh/frontend/projects"}]},
                ],
            },
        ],
    },

    # ══════════════════════════════════════════════════════════
    #  DATA ANALYST
    # ══════════════════════════════════════════════════════════
    "Data Analyst": {
        "title": "Data Analyst Roadmap",
        "title_ar": "خارطة طريق محلل البيانات",
        "stages": [
            {
                "order": 1, "title": "Data Fundamentals", "title_ar": "أساسيات البيانات",
                "description": "SQL and spreadsheets — the core tools of every data analyst.", "description_ar": "SQL وجداول البيانات — الأدوات الأساسية لكل محلل بيانات.",
                "tasks": [
                    {"order": 1, "title": "SQL for analysis", "title_ar": "SQL للتحليل", "description": "Complex queries, window functions, CTEs, and subqueries.", "description_ar": "الاستعلامات المعقدة، دوال النوافذ، CTEs، والاستعلامات الفرعية.", "skill_name": "SQL", "resources": [{"type": "course", "title": "SQL for Data Analysis (Udacity)", "url": "https://www.udacity.com/course/sql-for-data-analysis--ud198"}, {"type": "article", "title": "Mode SQL Tutorial", "url": "https://mode.com/sql-tutorial"}]},
                    {"order": 2, "title": "Statistics essentials", "title_ar": "أساسيات الإحصاء", "description": "Descriptive statistics, probability, distributions, hypothesis testing.", "description_ar": "الإحصاء الوصفي، الاحتمالات، التوزيعات، واختبار الفرضيات.", "skill_name": "Statistics", "resources": [{"type": "course", "title": "Statistics with Python (Coursera)", "url": "https://www.coursera.org/specializations/statistics-with-python"}]},
                ],
            },
            {
                "order": 2, "title": "Python for Data Analysis", "title_ar": "بايثون لتحليل البيانات",
                "description": "Automate analysis and handle larger datasets with Python.", "description_ar": "أتمتة التحليل والتعامل مع مجموعات بيانات أكبر باستخدام بايثون.",
                "tasks": [
                    {"order": 1, "title": "Python + Pandas", "title_ar": "بايثون + Pandas", "description": "DataFrames, cleaning, merging, grouping, and transforming data.", "description_ar": "إطارات البيانات، التنظيف، الدمج، التجميع، وتحويل البيانات.", "skill_name": "Pandas", "resources": [{"type": "course", "title": "Data Analysis with Python (freeCodeCamp)", "url": "https://www.freecodecamp.org/learn/data-analysis-with-python/"}]},
                    {"order": 2, "title": "Python fundamentals", "title_ar": "أساسيات بايثون", "description": "Core Python for scripting, data manipulation, and automation.", "description_ar": "أساسيات بايثون للبرمجة النصية ومعالجة البيانات والأتمتة.", "skill_name": "Python", "resources": [{"type": "course", "title": "Python for Data Science (IBM on Coursera)", "url": "https://www.coursera.org/learn/python-for-applied-data-science-ai"}]},
                ],
            },
            {
                "order": 3, "title": "Data Visualization", "title_ar": "تصوير البيانات",
                "description": "Tell stories with data — the most visible part of your work.", "description_ar": "احكِ قصصاً بالبيانات — الجزء الأكثر ظهوراً من عملك.",
                "tasks": [
                    {"order": 1, "title": "Power BI dashboards", "title_ar": "لوحات معلومات Power BI", "description": "Data modeling, DAX basics, interactive dashboards, and report design.", "description_ar": "نمذجة البيانات، أساسيات DAX، لوحات المعلومات التفاعلية، وتصميم التقارير.", "skill_name": "Power BI", "resources": [{"type": "course", "title": "Microsoft Power BI Learning Path", "url": "https://learn.microsoft.com/en-us/training/powerplatform/power-bi"}]},
                    {"order": 2, "title": "Tableau fundamentals", "title_ar": "أساسيات Tableau", "description": "Connecting data, building charts, dashboards, and calculated fields.", "description_ar": "ربط البيانات، بناء الرسوم البيانية، لوحات المعلومات، والحقول المحسوبة.", "skill_name": "Tableau", "resources": [{"type": "course", "title": "Tableau Free Training", "url": "https://www.tableau.com/learn/training/20244"}]},
                    {"order": 3, "title": "Data storytelling", "title_ar": "السرد القصصي بالبيانات", "description": "Chart selection, narrative structure, and presenting insights to stakeholders.", "description_ar": "اختيار الرسوم البيانية، هيكلة السرد، وعرض الرؤى لأصحاب المصلحة.", "skill_name": "Data Visualization", "resources": [{"type": "book", "title": "Storytelling with Data by Cole Nussbaumer Knaflic", "url": "https://www.storytellingwithdata.com/"}]},
                ],
            },
            {
                "order": 4, "title": "Portfolio & Job Readiness", "title_ar": "ملف الأعمال والجاهزية الوظيفية",
                "description": "Build real analysis projects and prepare for interviews.", "description_ar": "ابنِ مشاريع تحليل حقيقية واستعد للمقابلات.",
                "tasks": [
                    {"order": 1, "title": "End-to-end analysis project", "title_ar": "مشروع تحليل شامل", "description": "Pick a real dataset, clean it, analyze it, visualize findings, and present insights.", "description_ar": "اختر مجموعة بيانات حقيقية، نظّفها، حلّلها، صوّر النتائج، وقدّم الرؤى.", "skill_name": None, "resources": [{"type": "article", "title": "Kaggle Datasets", "url": "https://www.kaggle.com/datasets"}]},
                    {"order": 2, "title": "Build a data portfolio", "title_ar": "بناء ملف أعمال بيانات", "description": "Document 3+ projects with clear problem statements, methodologies, and findings.", "description_ar": "وثّق 3 مشاريع أو أكثر مع وصف واضح للمشكلة والمنهجية والنتائج.", "skill_name": None, "resources": [{"type": "article", "title": "Data Analytics Portfolio Guide", "url": "https://www.datacamp.com/blog/how-to-build-a-great-data-analyst-portfolio"}]},
                ],
            },
        ],
    },

    # ══════════════════════════════════════════════════════════
    #  MOBILE APP DEVELOPER
    # ══════════════════════════════════════════════════════════
    "Mobile App Developer": {
        "title": "Mobile App Developer Roadmap",
        "title_ar": "خارطة طريق مطوّر تطبيقات الجوال",
        "stages": [
            {
                "order": 1, "title": "Dart & Flutter Foundations", "title_ar": "أساسيات Dart و Flutter",
                "description": "Master the language and framework for cross-platform mobile development.", "description_ar": "أتقن اللغة وإطار العمل لتطوير تطبيقات الجوال متعددة المنصات.",
                "tasks": [
                    {"order": 1, "title": "Dart programming language", "title_ar": "لغة برمجة Dart", "description": "Variables, functions, classes, async/await, null safety, and collections.", "description_ar": "المتغيرات، الدوال، الفئات، async/await، أمان القيم الفارغة، والمجموعات.", "skill_name": "Dart", "resources": [{"type": "article", "title": "Dart Official Language Tour", "url": "https://dart.dev/language"}]},
                    {"order": 2, "title": "Flutter fundamentals", "title_ar": "أساسيات Flutter", "description": "Widgets, layouts, navigation, state management basics.", "description_ar": "الودجات، التخطيطات، التنقل، وأساسيات إدارة الحالة.", "skill_name": "Flutter", "resources": [{"type": "article", "title": "Flutter Official Codelabs", "url": "https://docs.flutter.dev/codelabs"}]},
                    {"order": 3, "title": "Git version control", "title_ar": "التحكم بالإصدارات باستخدام Git", "description": "Branching, merging, and collaboration workflows.", "description_ar": "التفرع، الدمج، وسير العمل التعاوني.", "skill_name": "Git", "resources": [{"type": "video", "title": "Git & GitHub for Beginners", "url": "https://www.youtube.com/watch?v=RGOj5yH7evk"}]},
                ],
            },
            {
                "order": 2, "title": "State Management & Architecture", "title_ar": "إدارة الحالة والهندسة المعمارية",
                "description": "Build scalable apps with proper architecture patterns.", "description_ar": "ابنِ تطبيقات قابلة للتوسع بأنماط هندسية صحيحة.",
                "tasks": [
                    {"order": 1, "title": "State management (Provider / Riverpod / Bloc)", "title_ar": "إدارة الحالة (Provider / Riverpod / Bloc)", "description": "Learn at least one state management solution deeply.", "description_ar": "تعلّم حلاً واحداً على الأقل لإدارة الحالة بعمق.", "skill_name": "Flutter", "resources": [{"type": "article", "title": "Flutter State Management Guide", "url": "https://docs.flutter.dev/data-and-backend/state-mgmt"}]},
                    {"order": 2, "title": "Backend integration with Firebase", "title_ar": "التكامل مع Firebase", "description": "Authentication, Firestore, Cloud Storage, and push notifications.", "description_ar": "المصادقة، Firestore، التخزين السحابي، والإشعارات.", "skill_name": "Firebase", "resources": [{"type": "article", "title": "FlutterFire Documentation", "url": "https://firebase.flutter.dev/docs/overview"}]},
                ],
            },
            {
                "order": 3, "title": "Advanced Flutter", "title_ar": "Flutter المتقدم",
                "description": "Animations, platform channels, and performance optimization.", "description_ar": "الرسوم المتحركة، قنوات المنصة، وتحسين الأداء.",
                "tasks": [
                    {"order": 1, "title": "Custom animations & UI", "title_ar": "رسوم متحركة وواجهات مخصصة", "description": "Implicit/explicit animations, custom painters, hero transitions.", "description_ar": "الرسوم المتحركة الضمنية والصريحة، الرسامون المخصصون، وانتقالات Hero.", "skill_name": "Flutter", "resources": [{"type": "article", "title": "Flutter Animations Guide", "url": "https://docs.flutter.dev/ui/animations"}]},
                    {"order": 2, "title": "App design with Figma", "title_ar": "تصميم التطبيق باستخدام Figma", "description": "Design your app screens before coding — wireframes and prototypes.", "description_ar": "صمّم شاشات تطبيقك قبل البرمجة — إطارات سلكية ونماذج أولية.", "skill_name": "Figma", "resources": [{"type": "video", "title": "Figma for Beginners", "url": "https://www.youtube.com/watch?v=FTFaQWZBqQ8"}]},
                ],
            },
            {
                "order": 4, "title": "Publish & Portfolio", "title_ar": "النشر وملف الأعمال",
                "description": "Ship a real app to the stores and build your developer portfolio.", "description_ar": "انشر تطبيقاً حقيقياً على المتاجر وابنِ ملف أعمالك كمطوّر.",
                "tasks": [
                    {"order": 1, "title": "Build and publish an app", "title_ar": "بناء ونشر تطبيق", "description": "Build a complete app, write tests, and publish to Google Play / App Store.", "description_ar": "ابنِ تطبيقاً كاملاً، اكتب اختبارات، وانشره على Google Play / App Store.", "skill_name": None, "resources": [{"type": "article", "title": "Flutter Deployment Guide", "url": "https://docs.flutter.dev/deployment"}]},
                ],
            },
        ],
    },

    # ══════════════════════════════════════════════════════════
    #  DATA SCIENTIST
    # ══════════════════════════════════════════════════════════
    "Data Scientist": {
        "title": "Data Scientist Roadmap",
        "title_ar": "خارطة طريق عالم البيانات",
        "stages": [
            {
                "order": 1, "title": "Math & Programming Foundations", "title_ar": "أساسيات الرياضيات والبرمجة",
                "description": "Statistics and Python — the bedrock of data science.", "description_ar": "الإحصاء وبايثون — الأساس الذي يُبنى عليه علم البيانات.",
                "tasks": [
                    {"order": 1, "title": "Python for data science", "title_ar": "بايثون لعلم البيانات", "description": "NumPy, Pandas, and Matplotlib for data manipulation.", "description_ar": "NumPy وPandas وMatplotlib لمعالجة البيانات.", "skill_name": "Python", "resources": [{"type": "course", "title": "Python for Data Science (IBM)", "url": "https://www.coursera.org/learn/python-for-applied-data-science-ai"}]},
                    {"order": 2, "title": "Statistics & probability", "title_ar": "الإحصاء والاحتمالات", "description": "Distributions, hypothesis testing, Bayesian thinking, regression.", "description_ar": "التوزيعات، اختبار الفرضيات، التفكير البايزي، والانحدار.", "skill_name": "Statistics", "resources": [{"type": "course", "title": "Statistics with Python (Coursera)", "url": "https://www.coursera.org/specializations/statistics-with-python"}]},
                    {"order": 3, "title": "SQL for data access", "title_ar": "SQL للوصول إلى البيانات", "description": "Querying databases, joins, and aggregations.", "description_ar": "استعلام قواعد البيانات، الربط، والتجميع.", "skill_name": "SQL", "resources": [{"type": "article", "title": "SQLBolt", "url": "https://sqlbolt.com/"}]},
                ],
            },
            {
                "order": 2, "title": "Machine Learning Fundamentals", "title_ar": "أساسيات تعلم الآلة",
                "description": "Core ML algorithms and when to use them.", "description_ar": "خوارزميات تعلم الآلة الأساسية ومتى تستخدمها.",
                "tasks": [
                    {"order": 1, "title": "Supervised learning", "title_ar": "التعلم المُراقب", "description": "Linear/logistic regression, decision trees, random forests, SVM.", "description_ar": "الانحدار الخطي/اللوجستي، أشجار القرار، الغابات العشوائية، SVM.", "skill_name": "Machine Learning", "resources": [{"type": "course", "title": "Machine Learning (Andrew Ng)", "url": "https://www.coursera.org/learn/machine-learning"}]},
                    {"order": 2, "title": "Unsupervised learning & evaluation", "title_ar": "التعلم غير المُراقب والتقييم", "description": "Clustering, PCA, cross-validation, metrics.", "description_ar": "التجميع، PCA، التحقق المتقاطع، ومقاييس الأداء.", "skill_name": "Machine Learning", "resources": [{"type": "course", "title": "ML Specialization (Coursera)", "url": "https://www.coursera.org/specializations/machine-learning-introduction"}]},
                    {"order": 3, "title": "Data visualization", "title_ar": "تصوير البيانات", "description": "Matplotlib, Seaborn, and Plotly for presenting findings.", "description_ar": "Matplotlib وSeaborn وPlotly لعرض النتائج.", "skill_name": "Data Visualization", "resources": [{"type": "article", "title": "Python Graph Gallery", "url": "https://python-graph-gallery.com/"}]},
                ],
            },
            {
                "order": 3, "title": "Deep Learning", "title_ar": "التعلم العميق",
                "description": "Neural networks for complex pattern recognition tasks.", "description_ar": "الشبكات العصبية للتعرف على الأنماط المعقدة.",
                "tasks": [
                    {"order": 1, "title": "TensorFlow / Keras basics", "title_ar": "أساسيات TensorFlow / Keras", "description": "Build, train, and evaluate neural networks.", "description_ar": "بناء وتدريب وتقييم الشبكات العصبية.", "skill_name": "TensorFlow", "resources": [{"type": "course", "title": "Deep Learning Specialization (Andrew Ng)", "url": "https://www.coursera.org/specializations/deep-learning"}]},
                    {"order": 2, "title": "PyTorch fundamentals", "title_ar": "أساسيات PyTorch", "description": "Tensors, autograd, model training loop, and custom datasets.", "description_ar": "المُوتّرات، التفاضل التلقائي، حلقة التدريب، ومجموعات البيانات المخصصة.", "skill_name": "PyTorch", "resources": [{"type": "article", "title": "PyTorch Official Tutorials", "url": "https://pytorch.org/tutorials/"}]},
                ],
            },
            {
                "order": 4, "title": "Projects & Specialization", "title_ar": "المشاريع والتخصص",
                "description": "Build end-to-end ML projects and develop a specialization.", "description_ar": "ابنِ مشاريع تعلم آلة شاملة وطوّر تخصصك.",
                "tasks": [
                    {"order": 1, "title": "Kaggle competitions", "title_ar": "مسابقات Kaggle", "description": "Participate in 2-3 competitions to test your skills against real problems.", "description_ar": "شارك في 2-3 مسابقات لاختبار مهاراتك على مشاكل حقيقية.", "skill_name": None, "resources": [{"type": "article", "title": "Kaggle Competitions", "url": "https://www.kaggle.com/competitions"}]},
                    {"order": 2, "title": "End-to-end ML project", "title_ar": "مشروع تعلم آلة شامل", "description": "Problem framing → data collection → modeling → deployment → documentation.", "description_ar": "تأطير المشكلة ← جمع البيانات ← النمذجة ← النشر ← التوثيق.", "skill_name": None, "resources": [{"type": "article", "title": "ML Project Checklist", "url": "https://www.fast.ai/posts/2020-01-07-data-questionnaire.html"}]},
                ],
            },
        ],
    },

    # ══════════════════════════════════════════════════════════
    #  UI/UX DESIGNER
    # ══════════════════════════════════════════════════════════
    "UI/UX Designer": {
        "title": "UI/UX Designer Roadmap",
        "title_ar": "خارطة طريق مصمم UI/UX",
        "stages": [
            {
                "order": 1, "title": "Design Thinking & Research", "title_ar": "التفكير التصميمي والبحث",
                "description": "Understand users before designing solutions.", "description_ar": "افهم المستخدمين قبل تصميم الحلول.",
                "tasks": [
                    {"order": 1, "title": "User research methods", "title_ar": "أساليب بحث المستخدمين", "description": "Interviews, surveys, personas, empathy maps, and journey maps.", "description_ar": "المقابلات، الاستبيانات، شخصيات المستخدمين، خرائط التعاطف، وخرائط الرحلة.", "skill_name": "User Research", "resources": [{"type": "course", "title": "Google UX Design Certificate", "url": "https://www.coursera.org/professional-certificates/google-ux-design"}]},
                    {"order": 2, "title": "Usability testing", "title_ar": "اختبار قابلية الاستخدام", "description": "Task-based testing, think-aloud protocol, and analyzing results.", "description_ar": "الاختبار المبني على المهام، بروتوكول التفكير بصوت عالٍ، وتحليل النتائج.", "skill_name": "Usability Testing", "resources": [{"type": "article", "title": "Nielsen Norman Group – Usability Testing", "url": "https://www.nngroup.com/articles/usability-testing-101/"}]},
                ],
            },
            {
                "order": 2, "title": "Wireframing & Prototyping", "title_ar": "الإطارات السلكية والنماذج الأولية",
                "description": "Turn research insights into tangible design concepts.", "description_ar": "حوّل رؤى البحث إلى مفاهيم تصميم ملموسة.",
                "tasks": [
                    {"order": 1, "title": "Figma fundamentals", "title_ar": "أساسيات Figma", "description": "Frames, components, auto-layout, constraints, and prototyping.", "description_ar": "الإطارات، المكونات، التخطيط التلقائي، القيود، والنماذج الأولية.", "skill_name": "Figma", "resources": [{"type": "video", "title": "Figma UI Design Tutorial (freeCodeCamp)", "url": "https://www.youtube.com/watch?v=jwCmIBJ8Jtc"}]},
                    {"order": 2, "title": "Wireframing techniques", "title_ar": "تقنيات الإطارات السلكية", "description": "Low-fi to high-fi wireframes, information architecture.", "description_ar": "من الإطارات منخفضة الدقة إلى عالية الدقة، وهندسة المعلومات.", "skill_name": "Wireframing", "resources": [{"type": "article", "title": "Wireframing Guide (Figma)", "url": "https://www.figma.com/resource-library/wireframing/"}]},
                    {"order": 3, "title": "Interactive prototyping", "title_ar": "النماذج الأولية التفاعلية", "description": "Clickable prototypes, transitions, and micro-interactions.", "description_ar": "نماذج أولية قابلة للنقر، الانتقالات، والتفاعلات الدقيقة.", "skill_name": "Prototyping", "resources": [{"type": "article", "title": "Figma Prototyping Guide", "url": "https://help.figma.com/hc/en-us/articles/360040314193-Guide-to-prototyping-in-Figma"}]},
                ],
            },
            {
                "order": 3, "title": "Visual Design & Systems", "title_ar": "التصميم المرئي والأنظمة",
                "description": "Create polished, consistent, and accessible interfaces.", "description_ar": "أنشئ واجهات متقنة ومتسقة وسهلة الوصول.",
                "tasks": [
                    {"order": 1, "title": "Design systems", "title_ar": "أنظمة التصميم", "description": "Component libraries, tokens, style guides, and documentation.", "description_ar": "مكتبات المكونات، الرموز، أدلة الأسلوب، والتوثيق.", "skill_name": "Design Systems", "resources": [{"type": "article", "title": "Design Systems 101 (NNg)", "url": "https://www.nngroup.com/articles/design-systems-101/"}]},
                    {"order": 2, "title": "Accessibility (WCAG)", "title_ar": "إمكانية الوصول (WCAG)", "description": "Color contrast, keyboard navigation, screen readers, and ARIA.", "description_ar": "تباين الألوان، التنقل بلوحة المفاتيح، قارئات الشاشة، و ARIA.", "skill_name": "Accessibility (WCAG)", "resources": [{"type": "article", "title": "Web Accessibility by Google (Udacity)", "url": "https://www.udacity.com/course/web-accessibility--ud891"}]},
                ],
            },
            {
                "order": 4, "title": "Portfolio & Case Studies", "title_ar": "ملف الأعمال ودراسات الحالة",
                "description": "Showcase your process, not just your pretty screens.", "description_ar": "اعرض عمليتك التصميمية، وليس فقط شاشاتك الجميلة.",
                "tasks": [
                    {"order": 1, "title": "Build 3 case studies", "title_ar": "بناء 3 دراسات حالة", "description": "Document your design process: research → ideation → testing → iteration.", "description_ar": "وثّق عمليتك التصميمية: بحث ← توليد أفكار ← اختبار ← تكرار.", "skill_name": None, "resources": [{"type": "article", "title": "UX Portfolio Guide", "url": "https://www.uxdesigninstitute.com/blog/ux-portfolio-guide/"}]},
                ],
            },
        ],
    },

    # ══════════════════════════════════════════════════════════
    #  CLOUD ENGINEER
    # ══════════════════════════════════════════════════════════
    "Cloud Engineer": {
        "title": "Cloud Engineer Roadmap",
        "title_ar": "خارطة طريق مهندس الحوسبة السحابية",
        "stages": [
            {
                "order": 1, "title": "Linux & Networking Foundations", "title_ar": "أساسيات لينكس والشبكات",
                "description": "Cloud runs on Linux — build your foundation here.", "description_ar": "السحابة تعمل على لينكس — ابنِ أساسك هنا.",
                "tasks": [
                    {"order": 1, "title": "Linux administration", "title_ar": "إدارة لينكس", "description": "Command line, file systems, permissions, processes, and shell scripting.", "description_ar": "سطر الأوامر، أنظمة الملفات، الصلاحيات، العمليات، وبرمجة الشل.", "skill_name": "Linux Administration", "resources": [{"type": "course", "title": "Linux for Beginners (Udemy)", "url": "https://www.udemy.com/course/linux-for-beginners/"}]},
                    {"order": 2, "title": "Networking fundamentals", "title_ar": "أساسيات الشبكات", "description": "TCP/IP, DNS, HTTP, subnets, load balancers, and firewalls.", "description_ar": "TCP/IP، DNS، HTTP، الشبكات الفرعية، موازنات الأحمال، والجدران النارية.", "skill_name": None, "resources": [{"type": "course", "title": "Computer Networking (Coursera)", "url": "https://www.coursera.org/learn/computer-networking"}]},
                ],
            },
            {
                "order": 2, "title": "AWS Core Services", "title_ar": "خدمات AWS الأساسية",
                "description": "Learn the most popular cloud platform's essential services.", "description_ar": "تعلّم الخدمات الأساسية لأكثر منصة سحابية شيوعاً.",
                "tasks": [
                    {"order": 1, "title": "AWS fundamentals", "title_ar": "أساسيات AWS", "description": "EC2, S3, VPC, IAM, RDS — the core building blocks.", "description_ar": "EC2، S3، VPC، IAM، RDS — اللبنات الأساسية.", "skill_name": "AWS", "resources": [{"type": "course", "title": "AWS Cloud Practitioner Essentials", "url": "https://aws.amazon.com/training/digital/aws-cloud-practitioner-essentials/"}]},
                    {"order": 2, "title": "Azure or GCP basics", "title_ar": "أساسيات Azure أو GCP", "description": "Learn a second cloud platform for breadth.", "description_ar": "تعلّم منصة سحابية ثانية لتوسيع معرفتك.", "skill_name": "Azure", "resources": [{"type": "course", "title": "Azure Fundamentals (Microsoft Learn)", "url": "https://learn.microsoft.com/en-us/training/paths/az-900-describe-cloud-concepts/"}]},
                ],
            },
            {
                "order": 3, "title": "Containers & Orchestration", "title_ar": "الحاويات والتنسيق",
                "description": "Modern cloud workloads run in containers.", "description_ar": "أحمال العمل السحابية الحديثة تعمل في حاويات.",
                "tasks": [
                    {"order": 1, "title": "Docker mastery", "title_ar": "إتقان Docker", "description": "Build, run, and compose multi-container applications.", "description_ar": "بناء وتشغيل وتنسيق تطبيقات متعددة الحاويات.", "skill_name": "Docker", "resources": [{"type": "video", "title": "Docker Tutorial (TechWorld with Nana)", "url": "https://www.youtube.com/watch?v=3c-iBn73dDE"}]},
                    {"order": 2, "title": "Kubernetes fundamentals", "title_ar": "أساسيات Kubernetes", "description": "Pods, deployments, services, ingress, and Helm charts.", "description_ar": "Pods، عمليات النشر، الخدمات، Ingress، ومخططات Helm.", "skill_name": "Kubernetes", "resources": [{"type": "course", "title": "Kubernetes for Beginners (KodeKloud)", "url": "https://kodekloud.com/courses/kubernetes-for-the-absolute-beginners/"}]},
                ],
            },
            {
                "order": 4, "title": "Infrastructure as Code", "title_ar": "البنية التحتية كرمز",
                "description": "Automate everything — never click in a console again.", "description_ar": "أتمت كل شيء — لا تنقر في وحدة التحكم مرة أخرى.",
                "tasks": [
                    {"order": 1, "title": "Terraform", "title_ar": "Terraform", "description": "Write, plan, and apply infrastructure across cloud providers.", "description_ar": "اكتب وخطط وطبّق البنية التحتية عبر مزودي السحابة.", "skill_name": "Terraform", "resources": [{"type": "article", "title": "HashiCorp Terraform Tutorials", "url": "https://developer.hashicorp.com/terraform/tutorials"}]},
                    {"order": 2, "title": "CI/CD for infrastructure", "title_ar": "CI/CD للبنية التحتية", "description": "GitOps, automated deployments, and infrastructure pipelines.", "description_ar": "GitOps، النشر التلقائي، وأنابيب البنية التحتية.", "skill_name": "CI/CD", "resources": [{"type": "article", "title": "GitHub Actions for Terraform", "url": "https://developer.hashicorp.com/terraform/tutorials/automation/github-actions"}]},
                ],
            },
        ],
    },

    # ══════════════════════════════════════════════════════════
    #  PRODUCT MANAGER
    # ══════════════════════════════════════════════════════════
    "Product Manager": {
        "title": "Product Manager Roadmap",
        "title_ar": "خارطة طريق مدير المنتجات",
        "stages": [
            {
                "order": 1, "title": "Product Thinking Foundations", "title_ar": "أساسيات التفكير المنتجي",
                "description": "Learn how to identify problems worth solving.", "description_ar": "تعلّم كيف تحدد المشاكل التي تستحق الحل.",
                "tasks": [
                    {"order": 1, "title": "Requirements analysis", "title_ar": "تحليل المتطلبات", "description": "User stories, acceptance criteria, prioritization frameworks (RICE, MoSCoW).", "description_ar": "قصص المستخدمين، معايير القبول، أطر تحديد الأولويات (RICE، MoSCoW).", "skill_name": "Requirements Analysis", "resources": [{"type": "course", "title": "Digital Product Management (Coursera)", "url": "https://www.coursera.org/learn/uva-darden-digital-product-management"}]},
                    {"order": 2, "title": "User research for PMs", "title_ar": "بحث المستخدمين لمديري المنتجات", "description": "Customer interviews, surveys, and data-driven decision making.", "description_ar": "مقابلات العملاء، الاستبيانات، واتخاذ القرارات المبنية على البيانات.", "skill_name": "User Research", "resources": [{"type": "article", "title": "The Mom Test (book summary)", "url": "https://www.momtestbook.com/"}]},
                ],
            },
            {
                "order": 2, "title": "Agile & Execution", "title_ar": "أجايل والتنفيذ",
                "description": "Ship products with cross-functional teams.", "description_ar": "اشحن منتجات مع فرق متعددة التخصصات.",
                "tasks": [
                    {"order": 1, "title": "Agile / Scrum", "title_ar": "أجايل / سكرم", "description": "Sprints, stand-ups, retrospectives, backlog management.", "description_ar": "السبرنتات، الاجتماعات اليومية، المراجعات الاسترجاعية، وإدارة قائمة المهام.", "skill_name": "Agile / Scrum", "resources": [{"type": "course", "title": "Agile with Atlassian Jira (Coursera)", "url": "https://www.coursera.org/learn/agile-atlassian-jira"}]},
                    {"order": 2, "title": "Stakeholder management", "title_ar": "إدارة أصحاب المصلحة", "description": "Aligning teams, managing expectations, and communicating trade-offs.", "description_ar": "محاذاة الفرق، إدارة التوقعات، والتواصل حول المقايضات.", "skill_name": "Stakeholder Management", "resources": [{"type": "article", "title": "Stakeholder Management Guide (ProductPlan)", "url": "https://www.productplan.com/learn/stakeholder-management/"}]},
                ],
            },
            {
                "order": 3, "title": "Strategy & Metrics", "title_ar": "الاستراتيجية والمقاييس",
                "description": "Think bigger — vision, strategy, and measuring success.", "description_ar": "فكّر أكبر — الرؤية، الاستراتيجية، وقياس النجاح.",
                "tasks": [
                    {"order": 1, "title": "Strategic planning", "title_ar": "التخطيط الاستراتيجي", "description": "Product vision, roadmaps, competitive analysis, and market sizing.", "description_ar": "رؤية المنتج، خرائط الطريق، تحليل المنافسين، وتقدير حجم السوق.", "skill_name": "Strategic Planning", "resources": [{"type": "course", "title": "Product Strategy (Reforge)", "url": "https://www.reforge.com/product-strategy"}]},
                    {"order": 2, "title": "Data-driven decisions", "title_ar": "القرارات المبنية على البيانات", "description": "KPIs, A/B testing, funnel analysis, and product analytics.", "description_ar": "مؤشرات الأداء، اختبارات A/B، تحليل القمع، وتحليلات المنتج.", "skill_name": "Communication", "resources": [{"type": "article", "title": "Product Analytics Guide (Amplitude)", "url": "https://amplitude.com/blog/product-analytics"}]},
                ],
            },
            {
                "order": 4, "title": "Portfolio & Networking", "title_ar": "ملف الأعمال والتواصل المهني",
                "description": "Build your PM brand and showcase your thinking.", "description_ar": "ابنِ علامتك كمدير منتجات واعرض طريقة تفكيرك.",
                "tasks": [
                    {"order": 1, "title": "PM case studies", "title_ar": "دراسات حالة PM", "description": "Write 2-3 product case studies showing your problem-solving approach.", "description_ar": "اكتب 2-3 دراسات حالة منتج تُظهر نهجك في حل المشاكل.", "skill_name": None, "resources": [{"type": "article", "title": "PM Case Study Guide (Exponent)", "url": "https://www.tryexponent.com/courses/pm-interview"}]},
                ],
            },
        ],
    },

    # ══════════════════════════════════════════════════════════
    #  SECURITY ANALYST
    # ══════════════════════════════════════════════════════════
    "Security Analyst": {
        "title": "Security Analyst Roadmap",
        "title_ar": "خارطة طريق محلل الأمن السيبراني",
        "stages": [
            {
                "order": 1, "title": "Security Foundations", "title_ar": "أساسيات الأمن السيبراني",
                "description": "Understand networks, systems, and the threat landscape.", "description_ar": "افهم الشبكات والأنظمة ومشهد التهديدات.",
                "tasks": [
                    {"order": 1, "title": "Network security fundamentals", "title_ar": "أساسيات أمن الشبكات", "description": "Firewalls, IDS/IPS, VPNs, and network segmentation.", "description_ar": "الجدران النارية، أنظمة كشف/منع التسلل، VPN، وتقسيم الشبكات.", "skill_name": "Network Security", "resources": [{"type": "course", "title": "Google Cybersecurity Certificate", "url": "https://www.coursera.org/professional-certificates/google-cybersecurity"}]},
                    {"order": 2, "title": "Linux for security", "title_ar": "لينكس للأمن السيبراني", "description": "Command line, log analysis, file permissions, and process monitoring.", "description_ar": "سطر الأوامر، تحليل السجلات، صلاحيات الملفات، ومراقبة العمليات.", "skill_name": "Linux Administration", "resources": [{"type": "course", "title": "Linux Essentials for Cybersecurity", "url": "https://www.netacad.com/courses/os-it/ndg-linux-essentials"}]},
                ],
            },
            {
                "order": 2, "title": "Threat Detection & SIEM", "title_ar": "كشف التهديدات و SIEM",
                "description": "Learn to monitor, detect, and analyze security events.", "description_ar": "تعلّم المراقبة والكشف وتحليل الأحداث الأمنية.",
                "tasks": [
                    {"order": 1, "title": "SIEM fundamentals", "title_ar": "أساسيات SIEM", "description": "Log collection, correlation rules, dashboards, and alert triage.", "description_ar": "جمع السجلات، قواعد الارتباط، لوحات المعلومات، وفرز التنبيهات.", "skill_name": "SIEM", "resources": [{"type": "course", "title": "Splunk Fundamentals", "url": "https://www.splunk.com/en_us/training/courses/splunk-fundamentals-1.html"}]},
                    {"order": 2, "title": "Vulnerability assessment", "title_ar": "تقييم الثغرات", "description": "Scanning tools (Nessus, OpenVAS), risk scoring, and remediation.", "description_ar": "أدوات الفحص (Nessus، OpenVAS)، تسجيل المخاطر، والمعالجة.", "skill_name": "Vulnerability Assessment", "resources": [{"type": "article", "title": "OWASP Testing Guide", "url": "https://owasp.org/www-project-web-security-testing-guide/"}]},
                ],
            },
            {
                "order": 3, "title": "Incident Response", "title_ar": "الاستجابة للحوادث",
                "description": "Handle security incidents from detection to recovery.", "description_ar": "تعامل مع الحوادث الأمنية من الكشف إلى التعافي.",
                "tasks": [
                    {"order": 1, "title": "Incident response process", "title_ar": "عملية الاستجابة للحوادث", "description": "Preparation, identification, containment, eradication, recovery, lessons learned.", "description_ar": "التحضير، التحديد، الاحتواء، الاستئصال، التعافي، والدروس المستفادة.", "skill_name": "Incident Response", "resources": [{"type": "article", "title": "NIST Incident Response Guide", "url": "https://csrc.nist.gov/pubs/sp/800/61/r2/final"}]},
                ],
            },
            {
                "order": 4, "title": "Certification & Career", "title_ar": "الشهادات والمسيرة المهنية",
                "description": "Get certified to validate your skills.", "description_ar": "احصل على شهادة لإثبات مهاراتك.",
                "tasks": [
                    {"order": 1, "title": "CompTIA Security+ preparation", "title_ar": "التحضير لشهادة CompTIA Security+", "description": "Study for and pass the industry-standard entry-level security certification.", "description_ar": "ادرس واجتز شهادة الأمن السيبراني المعيارية للمستوى المبتدئ.", "skill_name": None, "resources": [{"type": "course", "title": "CompTIA Security+ (Professor Messer)", "url": "https://www.professormesser.com/security-plus/sy0-701/sy0-701-video/sy0-701-comptia-security-plus-course/"}]},
                ],
            },
        ],
    },

    # ══════════════════════════════════════════════════════════
    #  DEVOPS ENGINEER
    # ══════════════════════════════════════════════════════════
    "DevOps Engineer": {
        "title": "DevOps Engineer Roadmap",
        "title_ar": "خارطة طريق مهندس DevOps",
        "stages": [
            {
                "order": 1, "title": "Linux & Scripting", "title_ar": "لينكس والبرمجة النصية",
                "description": "DevOps lives in the terminal — master it.", "description_ar": "DevOps يعيش في الطرفية — أتقنها.",
                "tasks": [
                    {"order": 1, "title": "Linux administration", "title_ar": "إدارة لينكس", "description": "Shell scripting, systemd, networking, and package management.", "description_ar": "برمجة الشل، systemd، الشبكات، وإدارة الحزم.", "skill_name": "Linux Administration", "resources": [{"type": "course", "title": "Linux Administration (LinkedIn Learning)", "url": "https://www.linkedin.com/learning/topics/linux"}]},
                    {"order": 2, "title": "Python for automation", "title_ar": "بايثون للأتمتة", "description": "Scripting, file manipulation, API calls, and automation tasks.", "description_ar": "البرمجة النصية، معالجة الملفات، استدعاءات API، ومهام الأتمتة.", "skill_name": "Python", "resources": [{"type": "course", "title": "Automate the Boring Stuff with Python", "url": "https://automatetheboringstuff.com/"}]},
                    {"order": 3, "title": "Git workflows", "title_ar": "سير عمل Git", "description": "Branching strategies, GitFlow, trunk-based development.", "description_ar": "استراتيجيات التفرع، GitFlow، التطوير المبني على الجذع.", "skill_name": "Git", "resources": [{"type": "article", "title": "Atlassian Git Tutorials", "url": "https://www.atlassian.com/git/tutorials"}]},
                ],
            },
            {
                "order": 2, "title": "Containers & CI/CD", "title_ar": "الحاويات و CI/CD",
                "description": "Automate building, testing, and deploying software.", "description_ar": "أتمت بناء واختبار ونشر البرمجيات.",
                "tasks": [
                    {"order": 1, "title": "Docker", "title_ar": "Docker", "description": "Dockerfiles, multi-stage builds, docker-compose, registries.", "description_ar": "ملفات Dockerfile، البناء متعدد المراحل، docker-compose، السجلات.", "skill_name": "Docker", "resources": [{"type": "video", "title": "Docker Full Course (TechWorld with Nana)", "url": "https://www.youtube.com/watch?v=3c-iBn73dDE"}]},
                    {"order": 2, "title": "CI/CD pipelines", "title_ar": "أنابيب CI/CD", "description": "GitHub Actions, Jenkins, or GitLab CI — build and deploy automatically.", "description_ar": "GitHub Actions أو Jenkins أو GitLab CI — ابنِ وانشر تلقائياً.", "skill_name": "CI/CD", "resources": [{"type": "article", "title": "GitHub Actions Docs", "url": "https://docs.github.com/en/actions"}]},
                    {"order": 3, "title": "Jenkins", "title_ar": "Jenkins", "description": "Pipelines, Jenkinsfile, plugins, and integrations.", "description_ar": "الأنابيب، Jenkinsfile، الإضافات، والتكاملات.", "skill_name": "Jenkins", "resources": [{"type": "course", "title": "Jenkins Tutorial (KodeKloud)", "url": "https://kodekloud.com/courses/jenkins/"}]},
                ],
            },
            {
                "order": 3, "title": "Cloud & Orchestration", "title_ar": "السحابة والتنسيق",
                "description": "Deploy and manage workloads at scale.", "description_ar": "انشر وأدِر أحمال العمل على نطاق واسع.",
                "tasks": [
                    {"order": 1, "title": "AWS core services", "title_ar": "خدمات AWS الأساسية", "description": "EC2, S3, VPC, IAM, ECS/EKS — the DevOps essentials.", "description_ar": "EC2، S3، VPC، IAM، ECS/EKS — أساسيات DevOps.", "skill_name": "AWS", "resources": [{"type": "course", "title": "AWS Cloud Practitioner", "url": "https://aws.amazon.com/training/digital/aws-cloud-practitioner-essentials/"}]},
                    {"order": 2, "title": "Kubernetes", "title_ar": "Kubernetes", "description": "Pods, deployments, services, ConfigMaps, and Helm.", "description_ar": "Pods، عمليات النشر، الخدمات، ConfigMaps، و Helm.", "skill_name": "Kubernetes", "resources": [{"type": "course", "title": "CKA Prep Course (KodeKloud)", "url": "https://kodekloud.com/courses/certified-kubernetes-administrator-cka/"}]},
                ],
            },
            {
                "order": 4, "title": "Infrastructure as Code & Monitoring", "title_ar": "البنية التحتية كرمز والمراقبة",
                "description": "Automate infrastructure and observe everything.", "description_ar": "أتمت البنية التحتية وراقب كل شيء.",
                "tasks": [
                    {"order": 1, "title": "Terraform", "title_ar": "Terraform", "description": "Declarative infrastructure, state management, modules.", "description_ar": "البنية التحتية التصريحية، إدارة الحالة، والوحدات.", "skill_name": "Terraform", "resources": [{"type": "article", "title": "Terraform Tutorials", "url": "https://developer.hashicorp.com/terraform/tutorials"}]},
                    {"order": 2, "title": "GitHub Actions advanced", "title_ar": "GitHub Actions المتقدم", "description": "Reusable workflows, matrix builds, secrets management.", "description_ar": "سير العمل القابل لإعادة الاستخدام، البناء المصفوفي، وإدارة الأسرار.", "skill_name": "GitHub Actions", "resources": [{"type": "article", "title": "GitHub Actions Advanced", "url": "https://docs.github.com/en/actions/using-workflows"}]},
                ],
            },
        ],
    },

    # ══════════════════════════════════════════════════════════
    #  BUSINESS ANALYST
    # ══════════════════════════════════════════════════════════
    "Business Analyst": {
        "title": "Business Analyst Roadmap",
        "title_ar": "خارطة طريق محلل الأعمال",
        "stages": [
            {
                "order": 1, "title": "BA Foundations", "title_ar": "أساسيات تحليل الأعمال",
                "description": "Learn to bridge business needs and technical solutions.", "description_ar": "تعلّم الربط بين احتياجات العمل والحلول التقنية.",
                "tasks": [
                    {"order": 1, "title": "Requirements analysis", "title_ar": "تحليل المتطلبات", "description": "Elicitation techniques, user stories, use cases, acceptance criteria.", "description_ar": "تقنيات الاستنباط، قصص المستخدمين، حالات الاستخدام، ومعايير القبول.", "skill_name": "Requirements Analysis", "resources": [{"type": "course", "title": "Business Analysis Foundations (LinkedIn Learning)", "url": "https://www.linkedin.com/learning/business-analysis-foundations"}]},
                    {"order": 2, "title": "Business process modeling", "title_ar": "نمذجة العمليات التجارية", "description": "BPMN, flowcharts, swimlane diagrams, and process improvement.", "description_ar": "BPMN، المخططات الانسيابية، مخططات المسارات، وتحسين العمليات.", "skill_name": "Business Process Modeling", "resources": [{"type": "article", "title": "BPMN Guide (Camunda)", "url": "https://camunda.com/bpmn/"}]},
                ],
            },
            {
                "order": 2, "title": "Data & Communication Skills", "title_ar": "مهارات البيانات والتواصل",
                "description": "Make data-driven recommendations and communicate them clearly.", "description_ar": "قدّم توصيات مبنية على البيانات وتواصلها بوضوح.",
                "tasks": [
                    {"order": 1, "title": "SQL for business analysis", "title_ar": "SQL لتحليل الأعمال", "description": "Query databases to pull your own data instead of waiting for reports.", "description_ar": "استعلم قواعد البيانات لسحب بياناتك بنفسك بدلاً من انتظار التقارير.", "skill_name": "SQL", "resources": [{"type": "course", "title": "SQL for Business Analysis (Udemy)", "url": "https://www.udemy.com/course/sql-for-newbs/"}]},
                    {"order": 2, "title": "Power BI dashboards", "title_ar": "لوحات معلومات Power BI", "description": "Self-service analytics and stakeholder-facing dashboards.", "description_ar": "التحليلات الذاتية ولوحات المعلومات الموجهة لأصحاب المصلحة.", "skill_name": "Power BI", "resources": [{"type": "course", "title": "Power BI Learning Path", "url": "https://learn.microsoft.com/en-us/training/powerplatform/power-bi"}]},
                    {"order": 3, "title": "Stakeholder management", "title_ar": "إدارة أصحاب المصلحة", "description": "Managing expectations, facilitating workshops, and resolving conflicts.", "description_ar": "إدارة التوقعات، تيسير ورش العمل، وحل النزاعات.", "skill_name": "Stakeholder Management", "resources": [{"type": "article", "title": "BA Stakeholder Guide (IIBA)", "url": "https://www.iiba.org/"}]},
                ],
            },
            {
                "order": 3, "title": "Agile & Project Delivery", "title_ar": "أجايل وتسليم المشاريع",
                "description": "Work effectively in agile teams.", "description_ar": "اعمل بفعالية في فرق أجايل.",
                "tasks": [
                    {"order": 1, "title": "Agile / Scrum for BAs", "title_ar": "أجايل / سكرم لمحللي الأعمال", "description": "Sprint planning, backlog refinement, and the BA's role in agile.", "description_ar": "تخطيط السبرنت، تنقيح قائمة المهام، ودور محلل الأعمال في أجايل.", "skill_name": "Agile / Scrum", "resources": [{"type": "course", "title": "Agile with Atlassian Jira", "url": "https://www.coursera.org/learn/agile-atlassian-jira"}]},
                    {"order": 2, "title": "Communication & presentations", "title_ar": "التواصل والعروض التقديمية", "description": "Executive summaries, status reports, and data presentations.", "description_ar": "الملخصات التنفيذية، تقارير الحالة، وعروض البيانات.", "skill_name": "Communication", "resources": [{"type": "article", "title": "Presentation Skills for BAs", "url": "https://www.bridging-the-gap.com/"}]},
                ],
            },
            {
                "order": 4, "title": "Certification & Portfolio", "title_ar": "الشهادات وملف الأعمال",
                "description": "Validate your skills and build a professional portfolio.", "description_ar": "أثبت مهاراتك وابنِ ملف أعمال مهني.",
                "tasks": [
                    {"order": 1, "title": "CBAP or PMI-PBA preparation", "title_ar": "التحضير لشهادة CBAP أو PMI-PBA", "description": "Study for an industry-recognized BA certification.", "description_ar": "ادرس للحصول على شهادة تحليل أعمال معترف بها في المجال.", "skill_name": None, "resources": [{"type": "article", "title": "IIBA CBAP Certification", "url": "https://www.iiba.org/business-analysis-certifications/cbap/"}]},
                ],
            },
        ],
    },

    # ══════════════════════════════════════════════════════════
    #  FULL-STACK DEVELOPER
    # ══════════════════════════════════════════════════════════
    "Full-Stack Developer": {
        "title": "Full-Stack Developer Roadmap",
        "title_ar": "خارطة طريق المطوّر الشامل",
        "stages": [
            {
                "order": 1, "title": "Frontend Foundations", "title_ar": "أساسيات الواجهات الأمامية",
                "description": "Build user interfaces with modern web technologies.", "description_ar": "ابنِ واجهات مستخدم بتقنيات الويب الحديثة.",
                "tasks": [
                    {"order": 1, "title": "JavaScript mastery", "title_ar": "إتقان JavaScript", "description": "ES6+, async/await, DOM manipulation, and modern JS patterns.", "description_ar": "ES6+، async/await، التعامل مع DOM، وأنماط JS الحديثة.", "skill_name": "JavaScript", "resources": [{"type": "course", "title": "JavaScript (freeCodeCamp)", "url": "https://www.freecodecamp.org/learn/javascript-algorithms-and-data-structures-v8/"}]},
                    {"order": 2, "title": "React fundamentals", "title_ar": "أساسيات React", "description": "Components, hooks, state management, and routing.", "description_ar": "المكونات، الخطافات، إدارة الحالة، والتوجيه.", "skill_name": "React", "resources": [{"type": "article", "title": "React Official Docs", "url": "https://react.dev/learn"}]},
                    {"order": 3, "title": "TypeScript", "title_ar": "TypeScript", "description": "Add type safety to your JavaScript code.", "description_ar": "أضف أمان الأنواع لكود JavaScript الخاص بك.", "skill_name": "TypeScript", "resources": [{"type": "article", "title": "TypeScript Handbook", "url": "https://www.typescriptlang.org/docs/handbook/"}]},
                ],
            },
            {
                "order": 2, "title": "Backend & Databases", "title_ar": "الباك إند وقواعد البيانات",
                "description": "Build APIs and manage data.", "description_ar": "ابنِ APIs وأدِر البيانات.",
                "tasks": [
                    {"order": 1, "title": "Node.js & Express", "title_ar": "Node.js و Express", "description": "REST APIs, middleware, routing, and server-side JavaScript.", "description_ar": "REST APIs، الوسيط، التوجيه، وJavaScript من جانب الخادم.", "skill_name": "Node.js", "resources": [{"type": "course", "title": "Node.js (freeCodeCamp)", "url": "https://www.freecodecamp.org/learn/back-end-development-and-apis/"}]},
                    {"order": 2, "title": "Python backend alternative", "title_ar": "بديل بايثون للباك إند", "description": "FastAPI or Django for Python-based backends.", "description_ar": "FastAPI أو Django للباك إند المبني على بايثون.", "skill_name": "Python", "resources": [{"type": "article", "title": "FastAPI Tutorial", "url": "https://fastapi.tiangolo.com/tutorial/"}]},
                    {"order": 3, "title": "PostgreSQL", "title_ar": "PostgreSQL", "description": "Relational database design, queries, indexes, and migrations.", "description_ar": "تصميم قواعد البيانات العلائقية، الاستعلامات، الفهارس، والترحيل.", "skill_name": "PostgreSQL", "resources": [{"type": "article", "title": "PostgreSQL Tutorial", "url": "https://www.postgresqltutorial.com/"}]},
                ],
            },
            {
                "order": 3, "title": "DevOps & Deployment", "title_ar": "DevOps والنشر",
                "description": "Ship your full-stack apps to production.", "description_ar": "انشر تطبيقاتك الشاملة في بيئة الإنتاج.",
                "tasks": [
                    {"order": 1, "title": "Git workflows", "title_ar": "سير عمل Git", "description": "Branching, PRs, code review, and CI integration.", "description_ar": "التفرع، طلبات السحب، مراجعة الكود، وتكامل CI.", "skill_name": "Git", "resources": [{"type": "article", "title": "Atlassian Git Tutorials", "url": "https://www.atlassian.com/git/tutorials"}]},
                    {"order": 2, "title": "Docker basics", "title_ar": "أساسيات Docker", "description": "Containerize both frontend and backend for consistent deployments.", "description_ar": "احتوِ الواجهة الأمامية والخلفية في حاويات للنشر المتسق.", "skill_name": "Docker", "resources": [{"type": "video", "title": "Docker Crash Course", "url": "https://www.youtube.com/watch?v=3c-iBn73dDE"}]},
                ],
            },
            {
                "order": 4, "title": "Full-Stack Projects", "title_ar": "مشاريع شاملة",
                "description": "Build complete apps that showcase both frontend and backend skills.", "description_ar": "ابنِ تطبيقات كاملة تُظهر مهاراتك في الواجهة الأمامية والخلفية.",
                "tasks": [
                    {"order": 1, "title": "Build a full-stack SaaS app", "title_ar": "بناء تطبيق SaaS شامل", "description": "Auth, CRUD, real-time features, deployment — the whole stack.", "description_ar": "المصادقة، CRUD، ميزات الوقت الحقيقي، النشر — المكدس الكامل.", "skill_name": None, "resources": [{"type": "article", "title": "Full-Stack Project Ideas", "url": "https://roadmap.sh/full-stack/projects"}]},
                ],
            },
        ],
    },
}


def seed(db: Session | None = None):
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        print("Seeding roadmap templates (bilingual)...")

        for role_name, template_data in TEMPLATES.items():
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                print(f"  [SKIP] Role '{role_name}' not found in DB")
                continue

            existing = (
                db.query(RoadmapTemplate)
                .filter(RoadmapTemplate.role_id == role.id)
                .first()
            )
            if existing:
                existing.title = template_data["title"]
                existing.title_ar = template_data.get("title_ar")
                existing.stages_json = {"stages": template_data["stages"]}
                print(f"  [UPDATED] {role_name}")
            else:
                template = RoadmapTemplate(
                    role_id=role.id,
                    title=template_data["title"],
                    title_ar=template_data.get("title_ar"),
                    stages_json={"stages": template_data["stages"]},
                )
                db.add(template)
                print(f"  [CREATED] {role_name}")

        db.commit()
        print("\nRoadmap template seed complete!")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    seed()
