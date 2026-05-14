# app/routers/career/role_survey.py
#
# Role-discovery survey — deterministic scoring.
# Flow: pick major → answer major-specific questions → get top-3 role suggestions.
#
# Endpoints
# ─────────
#   GET  /career/role-survey/majors                     → list of 3 allowed majors
#   GET  /career/role-survey/questions?major=it|eng|biz → questions for that major
#   POST /career/role-survey/submit                      → SurveyResult (top-3 roles)
#
# No Alembic migration required — results returned inline, not persisted.

from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.career.role import Role

router = APIRouter(prefix="/career/role-survey", tags=["role-survey"])

# ── Major constants ───────────────────────────────────────────────────────────

MajorKey = Literal["it", "eng", "biz"]

_MAJORS = [
    {
        "key": "it",
        "label_en": "Information Technology / Computing",
        "label_ar": "تقنية المعلومات والحوسبة",
        "icon": "computer",
        "description_en": "Software, data, cybersecurity, networking, and IT systems.",
        "description_ar": "البرمجيات، البيانات، الأمن السيبراني، الشبكات، وأنظمة تقنية المعلومات.",
        "db_field_name": "Information Technology",
    },
    {
        "key": "eng",
        "label_en": "Engineering",
        "label_ar": "الهندسة",
        "icon": "engineering",
        "description_en": "Mechanical, electrical, civil, industrial, and project engineering.",
        "description_ar": "الهندسة الميكانيكية، الكهربائية، المدنية، الصناعية، وإدارة مشاريع الهندسة.",
        "db_field_name": "Engineering",
    },
    {
        "key": "biz",
        "label_en": "Business",
        "label_ar": "الأعمال",
        "icon": "business_center",
        "description_en": "Finance, marketing, project management, HR, and business analysis.",
        "description_ar": "التمويل، التسويق، إدارة المشاريع، الموارد البشرية، وتحليل الأعمال.",
        "db_field_name": "Business",
    },
]

_MAJOR_BY_KEY: dict[str, dict] = {m["key"]: m for m in _MAJORS}

# ── Role-key → display names + explanations ───────────────────────────────────

# Role display names — values MUST match name_en in the DB roles table exactly.
# Run `SELECT name_en FROM roles WHERE role_type = 'role'` to verify.
_ROLE_NAMES: dict[str, dict[str, str]] = {
    # ── IT / Computing (DB field: "Information Technology") ──────────────
    "software_dev":    {"en": "Full-Stack Developer",     "ar": "مطور متكامل"},
    "data_analyst":    {"en": "Data Analyst",             "ar": "محلل بيانات"},
    "cybersecurity":   {"en": "Security Analyst",         "ar": "محلل أمن"},
    "cloud_network":   {"en": "Cloud Engineer",           "ar": "مهندس سحابة"},
    "it_support":      {"en": "Systems Administrator",    "ar": "مدير أنظمة"},
    "systems_analyst": {"en": "Systems Analyst",          "ar": "محلل أنظمة"},
    "biz_analyst_it":  {"en": "IT Business Analyst",      "ar": "محلل أعمال تقني"},
    # ── Engineering (DB field: "Engineering") ────────────────────────────
    # Note: no Electrical Engineering domain in DB; "electrical" key maps to
    # Design Engineer (Mechanical domain) as the closest technical design role.
    "mechanical":      {"en": "Mechanical Engineer",      "ar": "مهندس ميكانيكي"},
    "electrical":      {"en": "Manufacturing Engineer",   "ar": "مهندس تصنيع"},
    "civil":           {"en": "Civil Engineer",           "ar": "مهندس مدني"},
    "industrial":      {"en": "Industrial Engineer",      "ar": "مهندس صناعي"},
    "eng_coord":       {"en": "Construction Manager",     "ar": "مدير إنشاء"},
    # ── Business (DB field: "Business") ──────────────────────────────────
    # Note: Marketing Specialist and HR Specialist are not in the DB catalog;
    # mapped to closest available roles.
    "financial":       {"en": "Financial Analyst",        "ar": "محلل مالي"},
    "marketing":       {"en": "Economic Analyst",         "ar": "محلل اقتصادي"},
    "biz_coord":       {"en": "Operations Manager",       "ar": "مدير عمليات"},
    "biz_analyst":     {"en": "IT Business Analyst",      "ar": "محلل أعمال تقني"},
    "operations":      {"en": "Administrative Manager",   "ar": "مدير إداري"},
    "hr":              {"en": "General Manager",          "ar": "مدير عام"},
}

_ROLE_EXPLANATIONS: dict[str, dict[str, str]] = {
    "software_dev":    {"en": "You enjoy building end-to-end software products — from backend logic to frontend experience — and want to ship things real people use.",
                        "ar": "تستمتع ببناء منتجات برمجية متكاملة — من المنطق الخلفي إلى تجربة الواجهة — وتريد إطلاق أشياء يستخدمها الناس."},
    "data_analyst":    {"en": "You love working with data to uncover insights and support smarter business decisions.",
                        "ar": "تحب العمل مع البيانات لاكتشاف الرؤى ودعم قرارات الأعمال الأذكى."},
    "cybersecurity":   {"en": "You're driven to detect threats, investigate incidents, and keep systems and people safe from digital attacks.",
                        "ar": "أنت مدفوع لاكتشاف التهديدات والتحقيق في الحوادث وحماية الأنظمة والناس من الهجمات الرقمية."},
    "cloud_network":   {"en": "You enjoy designing and managing cloud platforms, infrastructure-as-code, and scalable systems that keep everything running.",
                        "ar": "تستمتع بتصميم وإدارة منصات السحابة والبنية التحتية كرمز والأنظمة القابلة للتوسع."},
    "it_support":      {"en": "You enjoy managing IT infrastructure, user access, and system health — the backbone that keeps an organization running.",
                        "ar": "تستمتع بإدارة البنية التحتية لتقنية المعلومات وصلاحيات المستخدمين وصحة الأنظمة."},
    "systems_analyst": {"en": "You excel at bridging the gap between business needs and IT solutions.",
                        "ar": "تتميز في ردم الفجوة بين احتياجات الأعمال وحلول تقنية المعلومات."},
    "biz_analyst_it":  {"en": "You bridge the gap between IT and business — translating technical capabilities into solutions that improve processes and outcomes.",
                        "ar": "أنت الجسر بين تقنية المعلومات والأعمال — تترجم القدرات التقنية إلى حلول تحسّن العمليات والنتائج."},
    "mechanical":      {"en": "You enjoy designing and building mechanical systems and solving physical engineering challenges.",
                        "ar": "تستمتع بتصميم وبناء الأنظمة الميكانيكية وحل التحديات الهندسية المادية."},
    "electrical":      {"en": "You enjoy turning engineering designs into physical reality — optimizing production processes and improving manufacturing quality.",
                        "ar": "تستمتع بتحويل التصاميم الهندسية إلى واقع مادي — تحسين عمليات الإنتاج والجودة."},
    "civil":           {"en": "You want to design and build infrastructure that strengthens and improves communities.",
                        "ar": "تريد تصميم وبناء بنية تحتية تقوي المجتمعات وتحسّنها."},
    "industrial":      {"en": "You're passionate about improving manufacturing processes and operational efficiency.",
                        "ar": "أنت متحمس لتحسين عمليات التصنيع والكفاءة التشغيلية."},
    "eng_coord":       {"en": "You lead complex construction or engineering projects — coordinating teams, managing schedules, and delivering on time and budget.",
                        "ar": "تقود مشاريع إنشائية أو هندسية معقدة — تنسّق الفرق وتدير الجداول الزمنية وتسلّم في الوقت وضمن الميزانية."},
    "financial":       {"en": "You're drawn to financial analysis, forecasting, and making data-driven economic decisions.",
                        "ar": "أنت منجذب للتحليل المالي والتنبؤ واتخاذ القرارات الاقتصادية المبنية على البيانات."},
    "marketing":       {"en": "You enjoy analyzing markets, economic trends, and data to provide insights that drive strategic business decisions.",
                        "ar": "تستمتع بتحليل الأسواق والاتجاهات الاقتصادية والبيانات لتقديم رؤى تدفع قرارات الأعمال الاستراتيجية."},
    "biz_coord":       {"en": "You thrive managing the day-to-day operations of a business — optimizing processes, leading teams, and ensuring everything runs smoothly.",
                        "ar": "تزدهر في إدارة العمليات اليومية للأعمال — تحسين العمليات وقيادة الفرق وضمان سير كل شيء بسلاسة."},
    "biz_analyst":     {"en": "You analyse how technology and business processes intersect, translating needs into clear system requirements and solutions.",
                        "ar": "تحلّل كيف تتقاطع التكنولوجيا والعمليات التجارية، وتترجم الاحتياجات إلى متطلبات نظام وحلول واضحة."},
    "operations":      {"en": "You keep organizations running by managing administrative functions, coordinating resources, and ensuring policies and procedures are followed.",
                        "ar": "تحافظ على سير المنظمات من خلال إدارة الوظائف الإدارية وتنسيق الموارد وضمان اتباع السياسات والإجراءات."},
    "hr":              {"en": "You lead an organization or business unit — setting strategy, managing people, and driving overall performance and growth.",
                        "ar": "تقود منظمة أو وحدة أعمال — تضع الاستراتيجية وتدير الأشخاص وتدفع الأداء والنمو الكلي."},
}

# ── Per-major question banks ──────────────────────────────────────────────────

_QUESTIONS_IT: list[dict] = [
    {
        "id": "it_q1",
        "text_en": "Which activity sounds most enjoyable to you?",
        "text_ar": "أي نشاط يبدو الأكثر متعةً بالنسبة لك؟",
        "options": [
            {"id": "it_q1_a", "text_en": "Writing code and building software applications",
             "text_ar": "كتابة الكود وبناء تطبيقات البرمجيات", "roles": ["software_dev"]},
            {"id": "it_q1_b", "text_en": "Analyzing data to find trends and hidden insights",
             "text_ar": "تحليل البيانات للعثور على الاتجاهات والرؤى الخفية", "roles": ["data_analyst"]},
            {"id": "it_q1_c", "text_en": "Protecting systems and people from cyber threats",
             "text_ar": "حماية الأنظمة والناس من التهديدات الإلكترونية", "roles": ["cybersecurity"]},
            {"id": "it_q1_d", "text_en": "Setting up and managing networks and cloud infrastructure",
             "text_ar": "إعداد وإدارة الشبكات والبنية التحتية السحابية", "roles": ["cloud_network"]},
            {"id": "it_q1_e", "text_en": "Helping users solve technical problems and get more from technology",
             "text_ar": "مساعدة المستخدمين في حل المشكلات التقنية والاستفادة من التكنولوجيا", "roles": ["it_support"]},
        ],
    },
    {
        "id": "it_q2",
        "text_en": "How do you feel about writing code?",
        "text_ar": "كيف تشعر حيال كتابة الكود؟",
        "options": [
            {"id": "it_q2_a", "text_en": "I love it — I want to code every day",
             "text_ar": "أحبه — أريد البرمجة كل يوم", "roles": ["software_dev"]},
            {"id": "it_q2_b", "text_en": "I enjoy it but prefer working with data more",
             "text_ar": "أستمتع به لكنني أفضل العمل مع البيانات أكثر", "roles": ["data_analyst"]},
            {"id": "it_q2_c", "text_en": "I use it for scripts and security tools occasionally",
             "text_ar": "أستخدمه أحياناً للنصوص البرمجية وأدوات الأمان", "roles": ["cybersecurity", "systems_analyst"]},
            {"id": "it_q2_d", "text_en": "I prefer configuring systems over writing code",
             "text_ar": "أفضل تهيئة الأنظمة على كتابة الكود", "roles": ["cloud_network", "it_support"]},
            {"id": "it_q2_e", "text_en": "I prefer business and analysis work over coding",
             "text_ar": "أفضل عمل الأعمال والتحليل على البرمجة", "roles": ["biz_analyst_it", "systems_analyst"]},
        ],
    },
    {
        "id": "it_q3",
        "text_en": "Which area of technology excites you most?",
        "text_ar": "أي مجال تقني يثير اهتمامك أكثر؟",
        "options": [
            {"id": "it_q3_a", "text_en": "Mobile or web application development",
             "text_ar": "تطوير تطبيقات الجوال أو الويب", "roles": ["software_dev"]},
            {"id": "it_q3_b", "text_en": "Artificial intelligence and machine learning",
             "text_ar": "الذكاء الاصطناعي والتعلم الآلي", "roles": ["data_analyst", "software_dev"]},
            {"id": "it_q3_c", "text_en": "Network security and ethical hacking",
             "text_ar": "أمن الشبكات والاختراق الأخلاقي", "roles": ["cybersecurity"]},
            {"id": "it_q3_d", "text_en": "Cloud infrastructure, DevOps, and site reliability",
             "text_ar": "البنية التحتية السحابية وDevOps وموثوقية المواقع", "roles": ["cloud_network"]},
            {"id": "it_q3_e", "text_en": "Enterprise systems, IT service management, and ERP",
             "text_ar": "الأنظمة المؤسسية وإدارة خدمات تقنية المعلومات وERP", "roles": ["systems_analyst", "it_support", "biz_analyst_it"]},
        ],
    },
    {
        "id": "it_q4",
        "text_en": "What kind of project would you be most excited to work on?",
        "text_ar": "ما نوع المشروع الذي ستكون أكثر حماساً للعمل عليه؟",
        "options": [
            {"id": "it_q4_a", "text_en": "Building a new app or software platform from scratch",
             "text_ar": "بناء تطبيق جديد أو منصة برمجية من الصفر", "roles": ["software_dev"]},
            {"id": "it_q4_b", "text_en": "A real-time analytics dashboard for a business",
             "text_ar": "لوحة تحليلات في الوقت الفعلي لشركة", "roles": ["data_analyst", "biz_analyst_it"]},
            {"id": "it_q4_c", "text_en": "A full security audit and penetration test",
             "text_ar": "تدقيق أمني كامل واختبار اختراق", "roles": ["cybersecurity"]},
            {"id": "it_q4_d", "text_en": "Migrating a company's entire infrastructure to the cloud",
             "text_ar": "نقل البنية التحتية بأكملها لشركة إلى السحابة", "roles": ["cloud_network"]},
            {"id": "it_q4_e", "text_en": "Implementing an ERP or CRM system company-wide",
             "text_ar": "تطبيق نظام ERP أو CRM على مستوى الشركة", "roles": ["systems_analyst", "it_support"]},
        ],
    },
    {
        "id": "it_q5",
        "text_en": "How do you prefer to solve problems?",
        "text_ar": "كيف تفضل حل المشكلات؟",
        "options": [
            {"id": "it_q5_a", "text_en": "Writing clean algorithms and debugging code",
             "text_ar": "كتابة خوارزميات نظيفة وتصحيح الكود", "roles": ["software_dev"]},
            {"id": "it_q5_b", "text_en": "Querying and exploring data to find patterns",
             "text_ar": "الاستعلام عن البيانات واستكشافها لإيجاد الأنماط", "roles": ["data_analyst"]},
            {"id": "it_q5_c", "text_en": "Thinking like an attacker to find system vulnerabilities",
             "text_ar": "التفكير كمهاجم لإيجاد ثغرات النظام", "roles": ["cybersecurity"]},
            {"id": "it_q5_d", "text_en": "Diagnosing and fixing network or infrastructure failures",
             "text_ar": "تشخيص وإصلاح أعطال الشبكة أو البنية التحتية", "roles": ["cloud_network", "it_support"]},
            {"id": "it_q5_e", "text_en": "Gathering requirements and translating them into technical specs",
             "text_ar": "جمع المتطلبات وترجمتها إلى مواصفات تقنية", "roles": ["systems_analyst", "biz_analyst_it"]},
        ],
    },
    {
        "id": "it_q6",
        "text_en": "How do you feel about working with business stakeholders?",
        "text_ar": "كيف تشعر حيال العمل مع أصحاب المصلحة في الأعمال؟",
        "options": [
            {"id": "it_q6_a", "text_en": "I prefer to focus on coding with fewer meetings",
             "text_ar": "أفضل التركيز على البرمجة مع اجتماعات أقل", "roles": ["software_dev"]},
            {"id": "it_q6_b", "text_en": "I enjoy it when it involves data-driven decisions",
             "text_ar": "أستمتع به عندما يتضمن قرارات مبنية على البيانات", "roles": ["data_analyst", "biz_analyst_it"]},
            {"id": "it_q6_c", "text_en": "I'm fine with security briefings and compliance meetings",
             "text_ar": "أنا مرتاح لجلسات الإحاطة الأمنية واجتماعات الامتثال", "roles": ["cybersecurity"]},
            {"id": "it_q6_d", "text_en": "I mainly interact with them for infrastructure planning",
             "text_ar": "أتفاعل معهم بشكل رئيسي لتخطيط البنية التحتية", "roles": ["cloud_network"]},
            {"id": "it_q6_e", "text_en": "I love being the bridge between business teams and IT",
             "text_ar": "أحب أن أكون الجسر بين فرق الأعمال وتقنية المعلومات", "roles": ["systems_analyst", "biz_analyst_it"]},
        ],
    },
    # ── Adapted from CSM Q6 (consultant/troubleshooter vs leader) + Q20 (promotion vs challenge)
    {
        "id": "it_q7",
        "text_en": "Which IT career path feels most like you?",
        "text_ar": "أي مسار مهني في تقنية المعلومات يشبهك أكثر؟",
        "options": [
            {"id": "it_q7_a", "text_en": "I enjoy being the person who builds things — I want to code and create every day",
             "text_ar": "أستمتع بأن أكون الشخص الذي يبني الأشياء — أريد البرمجة والإنشاء كل يوم", "roles": ["software_dev"]},
            {"id": "it_q7_b", "text_en": "I want to be the go-to expert in data — finding insights no one else sees",
             "text_ar": "أريد أن أكون الخبير المرجعي في البيانات — إيجاد رؤى لا يراها أحد غيري", "roles": ["data_analyst"]},
            {"id": "it_q7_c", "text_en": "I enjoy being the 'trouble-shooter' — getting energized by high-stakes security challenges",
             "text_ar": "أستمتع بأن أكون 'حل المشكلات' — أشعر بالطاقة من تحديات الأمن عالية المخاطر", "roles": ["cybersecurity"]},
            {"id": "it_q7_d", "text_en": "I want to be responsible for the infrastructure that keeps everything running",
             "text_ar": "أريد أن أكون مسؤولاً عن البنية التحتية التي تجعل كل شيء يعمل", "roles": ["cloud_network", "it_support"]},
            {"id": "it_q7_e", "text_en": "I want to be the leader who bridges IT and business and drives organizational outcomes",
             "text_ar": "أريد أن أكون القائد الذي يربط تقنية المعلومات بالأعمال ويحقق النتائج التنظيمية", "roles": ["systems_analyst", "biz_analyst_it"]},
        ],
    },
    # ── Adapted from CSM Q28 (long-term steady team vs fast-paced short-term project) + Q11 (exciting projects vs own boss)
    {
        "id": "it_q8",
        "text_en": "Which work style fits you best?",
        "text_ar": "أي أسلوب عمل يناسبك أكثر؟",
        "options": [
            {"id": "it_q8_a", "text_en": "Fast-paced, varied projects — I get energized by new challenges and ship often",
             "text_ar": "مشاريع سريعة ومتنوعة — تشحنني التحديات الجديدة وأسلّم كثيراً", "roles": ["software_dev", "cybersecurity"]},
            {"id": "it_q8_b", "text_en": "Deep, independent focus work — I need long uninterrupted stretches to do my best thinking",
             "text_ar": "عمل تركيز عميق ومستقل — أحتاج إلى فترات طويلة دون انقطاع لأفكر بأفضل ما لدي", "roles": ["data_analyst", "software_dev"]},
            {"id": "it_q8_c", "text_en": "Long-term, stable work with a dedicated team maintaining critical systems",
             "text_ar": "عمل طويل الأمد ومستقر مع فريق متخصص يصون الأنظمة الحيوية", "roles": ["cloud_network", "it_support"]},
            {"id": "it_q8_d", "text_en": "Cross-functional collaboration — I thrive connecting different teams and translating between them",
             "text_ar": "التعاون متعدد الوظائف — أزدهر في توصيل الفرق المختلفة والترجمة بينها", "roles": ["systems_analyst", "biz_analyst_it"]},
            {"id": "it_q8_e", "text_en": "I prefer being my own boss as much as possible — consulting, freelancing, or high-autonomy roles",
             "text_ar": "أفضل أن أكون مديراً لنفسي قدر المستطاع — استشارات أو عمل مستقل أو أدوار ذات استقلالية عالية", "roles": ["cybersecurity", "data_analyst", "software_dev"]},
        ],
    },

    # ── Adapted from CSM Q3 (rewards hard work/loyalty vs own goals at own pace) + Q5 (work independently vs company person)
    {
        "id": "it_q9",
        "text_en": "Which statement best describes how you want to work in an IT career?",
        "text_ar": "أي عبارة تصف أفضل كيف تريد العمل في مسيرة تقنية المعلومات؟",
        "options": [
            {"id": "it_q9_a", "text_en": "I like being a company person — loyal, reliable, contributing steadily to an established team",
             "text_ar": "أحب أن أكون شخصاً مؤسسياً — وفياً وموثوقاً أساهم بثبات في فريق راسخ", "roles": ["it_support", "systems_analyst"]},
            {"id": "it_q9_b", "text_en": "I prefer to work independently — setting my own goals and working at my own pace",
             "text_ar": "أفضل العمل بشكل مستقل — أضع أهدافي الخاصة وأعمل بإيقاعي الخاص", "roles": ["software_dev", "data_analyst"]},
            {"id": "it_q9_c", "text_en": "I want to excel and become the recognized technical expert that others rely on",
             "text_ar": "أريد التميز وأن أصبح الخبير التقني المعترف به الذي يعتمد عليه الآخرون", "roles": ["cybersecurity", "data_analyst"]},
            {"id": "it_q9_d", "text_en": "I want an organization that rewards my hard work, dedication, and loyalty with long-term growth",
             "text_ar": "أريد منظمة تكافئ عملي الجاد وتفانيي وولائي بنمو طويل الأمد", "roles": ["cloud_network", "it_support", "systems_analyst"]},
            {"id": "it_q9_e", "text_en": "I want to make the organization's goals and my own personal goals converge — I thrive when both win",
             "text_ar": "أريد أن تتقاطع أهداف المنظمة وأهدافي الشخصية — أزدهر عندما يربح الطرفان", "roles": ["biz_analyst_it", "systems_analyst"]},
        ],
    },
    # ── Adapted from CSM Q19 (security and belonging vs family/personal time) + Q2 (leisure/relationships vs subordinating personal needs for advancement)
    {
        "id": "it_q10",
        "text_en": "What matters most to you when choosing an IT role?",
        "text_ar": "ما الأهم بالنسبة لك عند اختيار دور في تقنية المعلومات؟",
        "options": [
            {"id": "it_q10_a", "text_en": "Job security, stability, and a strong sense of belonging to a team I trust",
             "text_ar": "الأمن الوظيفي والاستقرار والانتماء القوي لفريق أثق به", "roles": ["it_support", "cloud_network"]},
            {"id": "it_q10_b", "text_en": "Work that energizes me — I'm happy to go the extra mile when the mission is exciting",
             "text_ar": "عمل يشحن طاقتي — أنا سعيد ببذل جهد إضافي عندما تكون المهمة مثيرة", "roles": ["cybersecurity", "software_dev"]},
            {"id": "it_q10_c", "text_en": "Being able to devote time to my personal life, relationships, and health alongside meaningful work",
             "text_ar": "القدرة على تخصيص وقت لحياتي الشخصية وعلاقاتي وصحتي إلى جانب عمل ذي معنى", "roles": ["data_analyst", "systems_analyst"]},
            {"id": "it_q10_d", "text_en": "Maximum control over when, where, and how I work",
             "text_ar": "أقصى سيطرة على متى وأين وكيف أعمل", "roles": ["software_dev", "data_analyst"]},
            {"id": "it_q10_e", "text_en": "A clear path to advance — I will subordinate some personal needs to get ahead in my career",
             "text_ar": "مسار واضح للتقدم — سأتنازل عن بعض الاحتياجات الشخصية للتقدم في مسيرتي المهنية", "roles": ["biz_analyst_it", "systems_analyst", "cybersecurity"]},
        ],
    },
]

_QUESTIONS_ENG: list[dict] = [
    {
        "id": "eng_q1",
        "text_en": "Which type of engineering work appeals most to you?",
        "text_ar": "أي نوع من العمل الهندسي يجذبك أكثر؟",
        "options": [
            {"id": "eng_q1_a", "text_en": "Designing mechanical parts, machines, and thermal systems",
             "text_ar": "تصميم الأجزاء الميكانيكية والآلات والأنظمة الحرارية", "roles": ["mechanical"]},
            {"id": "eng_q1_b", "text_en": "Working with electrical circuits, motors, and power systems",
             "text_ar": "العمل مع الدوائر الكهربائية والمحركات وأنظمة الطاقة", "roles": ["electrical"]},
            {"id": "eng_q1_c", "text_en": "Planning and building roads, bridges, or structures",
             "text_ar": "تخطيط وبناء الطرق والجسور أو الهياكل", "roles": ["civil"]},
            {"id": "eng_q1_d", "text_en": "Improving manufacturing processes and industrial operations",
             "text_ar": "تحسين عمليات التصنيع والعمليات الصناعية", "roles": ["industrial"]},
            {"id": "eng_q1_e", "text_en": "Coordinating engineering teams and managing project delivery",
             "text_ar": "تنسيق الفرق الهندسية وإدارة تسليم المشاريع", "roles": ["eng_coord"]},
        ],
    },
    {
        "id": "eng_q2",
        "text_en": "Which work environment do you prefer?",
        "text_ar": "أي بيئة عمل تفضلها؟",
        "options": [
            {"id": "eng_q2_a", "text_en": "An engineering design office with CAD and technical calculations",
             "text_ar": "مكتب تصميم هندسي مع CAD والحسابات التقنية", "roles": ["mechanical", "electrical"]},
            {"id": "eng_q2_b", "text_en": "Active construction sites and outdoor fieldwork",
             "text_ar": "مواقع البناء النشطة والعمل الميداني في الهواء الطلق", "roles": ["civil"]},
            {"id": "eng_q2_c", "text_en": "A manufacturing plant or industrial production facility",
             "text_ar": "مصنع أو منشأة إنتاج صناعي", "roles": ["industrial"]},
            {"id": "eng_q2_d", "text_en": "Moving between offices, sites, and multi-discipline project teams",
             "text_ar": "التنقل بين المكاتب والمواقع وفرق المشاريع متعددة التخصصات", "roles": ["eng_coord"]},
            {"id": "eng_q2_e", "text_en": "A research and development or testing laboratory",
             "text_ar": "مختبر بحث وتطوير أو اختبار", "roles": ["mechanical", "electrical"]},
        ],
    },
    {
        "id": "eng_q3",
        "text_en": "Which engineering subject excites you most?",
        "text_ar": "أي موضوع هندسي يثير اهتمامك أكثر؟",
        "options": [
            {"id": "eng_q3_a", "text_en": "Thermodynamics, fluid mechanics, or material science",
             "text_ar": "الديناميكا الحرارية أو ميكانيكا الموائع أو علم المواد", "roles": ["mechanical"]},
            {"id": "eng_q3_b", "text_en": "Circuit theory, power systems, or control engineering",
             "text_ar": "نظرية الدوائر أو أنظمة الطاقة أو هندسة التحكم", "roles": ["electrical"]},
            {"id": "eng_q3_c", "text_en": "Structural analysis, geotechnics, or transportation planning",
             "text_ar": "التحليل الإنشائي أو الجيوتقنية أو تخطيط النقل", "roles": ["civil"]},
            {"id": "eng_q3_d", "text_en": "Operations research, lean manufacturing, or systems engineering",
             "text_ar": "بحوث العمليات أو التصنيع الرشيق أو هندسة الأنظمة", "roles": ["industrial"]},
            {"id": "eng_q3_e", "text_en": "Project management, risk analysis, or systems integration",
             "text_ar": "إدارة المشاريع أو تحليل المخاطر أو تكامل الأنظمة", "roles": ["eng_coord"]},
        ],
    },
    {
        "id": "eng_q4",
        "text_en": "Which project outcome would make you most proud?",
        "text_ar": "أي نتيجة مشروع ستجعلك أكثر فخراً؟",
        "options": [
            {"id": "eng_q4_a", "text_en": "A machine or mechanical system running perfectly for years",
             "text_ar": "آلة أو نظام ميكانيكي يعمل بشكل مثالي لسنوات", "roles": ["mechanical"]},
            {"id": "eng_q4_b", "text_en": "An electrical system powering thousands of homes or a facility",
             "text_ar": "نظام كهربائي يوفر الطاقة لآلاف المنازل أو منشأة", "roles": ["electrical"]},
            {"id": "eng_q4_c", "text_en": "A bridge, dam, or major structure I helped design and build",
             "text_ar": "جسر أو سد أو هيكل رئيسي ساعدت في تصميمه وبنائه", "roles": ["civil"]},
            {"id": "eng_q4_d", "text_en": "Cutting factory downtime by 40% through process improvements",
             "text_ar": "تقليص وقت توقف المصنع بنسبة 40% من خلال تحسينات العمليات", "roles": ["industrial"]},
            {"id": "eng_q4_e", "text_en": "Delivering a complex multi-discipline engineering project on time",
             "text_ar": "تسليم مشروع هندسي متعدد التخصصات المعقد في الوقت المحدد", "roles": ["eng_coord"]},
        ],
    },
    {
        "id": "eng_q5",
        "text_en": "Which tool or skill would you most want to master?",
        "text_ar": "أي أداة أو مهارة تريد إتقانها أكثر؟",
        "options": [
            {"id": "eng_q5_a", "text_en": "SolidWorks, ANSYS, or advanced CAD/CAM for mechanical design",
             "text_ar": "SolidWorks أو ANSYS أو CAD/CAM المتقدم للتصميم الميكانيكي", "roles": ["mechanical"]},
            {"id": "eng_q5_b", "text_en": "AutoCAD Electrical, MATLAB, or PLC/SCADA programming",
             "text_ar": "AutoCAD Electrical أو MATLAB أو برمجة PLC/SCADA", "roles": ["electrical"]},
            {"id": "eng_q5_c", "text_en": "SAP2000, ETABS, or civil infrastructure design software",
             "text_ar": "SAP2000 أو ETABS أو برامج تصميم البنية التحتية المدنية", "roles": ["civil"]},
            {"id": "eng_q5_d", "text_en": "Lean / Six Sigma, Arena simulation, or quality management",
             "text_ar": "Lean / Six Sigma أو محاكاة Arena أو إدارة الجودة", "roles": ["industrial"]},
            {"id": "eng_q5_e", "text_en": "MS Project, Primavera P6, or PMI / Agile certifications",
             "text_ar": "MS Project أو Primavera P6 أو شهادات PMI / Agile", "roles": ["eng_coord"]},
        ],
    },
    {
        "id": "eng_q6",
        "text_en": "How do you feel about managing people and project budgets?",
        "text_ar": "كيف تشعر حيال إدارة الأشخاص وميزانيات المشاريع؟",
        "options": [
            {"id": "eng_q6_a", "text_en": "I prefer deep technical design work — less management",
             "text_ar": "أفضل العمل التصميمي التقني العميق — إدارة أقل", "roles": ["mechanical", "electrical"]},
            {"id": "eng_q6_b", "text_en": "Some coordination is fine but I mainly want technical work",
             "text_ar": "بعض التنسيق مقبول لكنني أريد بشكل رئيسي العمل التقني", "roles": ["civil", "industrial"]},
            {"id": "eng_q6_c", "text_en": "I enjoy leading teams and managing project deliverables",
             "text_ar": "أستمتع بقيادة الفرق وإدارة مخرجات المشاريع", "roles": ["eng_coord"]},
            {"id": "eng_q6_d", "text_en": "I want to move into project leadership eventually",
             "text_ar": "أريد الانتقال إلى قيادة المشاريع في نهاية المطاف", "roles": ["industrial", "eng_coord"]},
            {"id": "eng_q6_e", "text_en": "I prefer working independently on focused technical problems",
             "text_ar": "أفضل العمل بشكل مستقل على مشكلات تقنية محددة", "roles": ["mechanical", "electrical", "civil"]},
        ],
    },
    # ── Adapted from CSM Q15 (plans/organizes vs creative new solutions) + Q6 (troubleshooter vs leader)
    {
        "id": "eng_q7",
        "text_en": "Which engineering career path feels most like you?",
        "text_ar": "أي مسار مهني هندسي يشبهك أكثر؟",
        "options": [
            {"id": "eng_q7_a", "text_en": "I want to be the deep technical expert — designing and solving difficult engineering problems",
             "text_ar": "أريد أن أكون الخبير التقني العميق — أصمم وأحل المشكلات الهندسية الصعبة", "roles": ["mechanical", "electrical"]},
            {"id": "eng_q7_b", "text_en": "I want to be on-site — building, inspecting, and making things physically happen",
             "text_ar": "أريد أن أكون في الموقع — أبني وأفتش وأجعل الأشياء تحدث فعلياً", "roles": ["civil", "industrial"]},
            {"id": "eng_q7_c", "text_en": "I enjoy being the 'trouble-shooter' — getting energized by novel engineering challenges no one has solved",
             "text_ar": "أستمتع بدور 'حل المشكلات' — أشعر بالطاقة من التحديات الهندسية الجديدة التي لم يحلها أحد", "roles": ["mechanical", "electrical"]},
            {"id": "eng_q7_d", "text_en": "I want to plan, optimize, and improve how systems and processes operate",
             "text_ar": "أريد تخطيط وتحسين كيفية عمل الأنظمة والعمليات", "roles": ["industrial"]},
            {"id": "eng_q7_e", "text_en": "I want to lead — responsible for a team achieving a major engineering objective",
             "text_ar": "أريد أن أقود — مسؤولاً عن فريق يحقق هدفاً هندسياً رئيسياً", "roles": ["eng_coord"]},
        ],
    },
    # ── Adapted from CSM Q28 (long-term steady team vs fast-paced project) + Q20 (promotion vs challenging problems)
    {
        "id": "eng_q8",
        "text_en": "Which work style suits you best as an engineer?",
        "text_ar": "أي أسلوب عمل يناسبك أكثر كمهندس؟",
        "options": [
            {"id": "eng_q8_a", "text_en": "Long-term, steady work with a dedicated technical team — stability and depth matter more than variety",
             "text_ar": "عمل طويل الأمد ومستقر مع فريق تقني متخصص — الاستقرار والعمق أهم من التنوع", "roles": ["mechanical", "electrical", "civil"]},
            {"id": "eng_q8_b", "text_en": "Working with a fast-paced project group — high intensity, clear deliverable, then move to the next",
             "text_ar": "العمل مع مجموعة مشروع سريعة الوتيرة — كثافة عالية، مخرجات واضحة، ثم الانتقال للتالي", "roles": ["eng_coord", "industrial"]},
            {"id": "eng_q8_c", "text_en": "I prefer a career with potential to advance into leadership and management",
             "text_ar": "أفضل مساراً مهنياً بإمكانية التقدم نحو القيادة والإدارة", "roles": ["eng_coord"]},
            {"id": "eng_q8_d", "text_en": "I want the opportunity to tackle the hardest, most challenging engineering problems — advancement is secondary",
             "text_ar": "أريد الفرصة لمعالجة أصعب المشكلات الهندسية وأكثرها تحدياً — التقدم الوظيفي ثانوي", "roles": ["mechanical", "electrical"]},
            {"id": "eng_q8_e", "text_en": "I thrive in production or operations settings where I continuously improve real physical processes",
             "text_ar": "أزدهر في بيئات الإنتاج أو التشغيل حيث أحسّن العمليات المادية الحقيقية باستمرار", "roles": ["industrial", "civil"]},
        ],
    },

    # ── Adapted from CSM Q9 (competent/loyal/trustworthy vs politically skillful/good leader) + Q16 (expert in field vs solid citizen)
    {
        "id": "eng_q9",
        "text_en": "Which best describes your professional identity as an engineer?",
        "text_ar": "أيٌّ من هذه الخيارات يصف هويتك المهنية كمهندس؟",
        "options": [
            {"id": "eng_q9_a", "text_en": "I am competent, loyal, and hardworking — the backbone of any engineering team",
             "text_ar": "أنا كفء وأمين وجاد — العمود الفقري لأي فريق هندسي", "roles": ["civil", "industrial"]},
            {"id": "eng_q9_b", "text_en": "I am an expert in my specialization — people come to me for the deepest technical knowledge",
             "text_ar": "أنا خبير في تخصصي — يأتي الناس إليّ للمعرفة التقنية الأعمق", "roles": ["mechanical", "electrical"]},
            {"id": "eng_q9_c", "text_en": "I am politically skillful and a strong leader — I make things happen and align teams to a goal",
             "text_ar": "أنا ماهر سياسياً وقائد قوي — أجعل الأشياء تحدث وأوحّد الفرق نحو هدف", "roles": ["eng_coord"]},
            {"id": "eng_q9_d", "text_en": "I am a solid citizen — dependable, proud to be part of a respected engineering organization",
             "text_ar": "أنا مواطن صالح — موثوق وفخور بأن أكون جزءاً من منظمة هندسية محترمة", "roles": ["industrial", "civil"]},
            {"id": "eng_q9_e", "text_en": "I am imaginative and enthusiastic — I get excited by problems no one has solved before",
             "text_ar": "أنا مبدع ومتحمس — أشعر بالإثارة من المشكلات التي لم يحلها أحد من قبل", "roles": ["mechanical", "electrical"]},
        ],
    },
    # ── Adapted from CSM Q30 (equilibrium vs excitement/stimulation) + Q27 (excel in field vs dependable and loyal)
    {
        "id": "eng_q10",
        "text_en": "What drives you most at the end of the day as an engineer?",
        "text_ar": "ما الذي يدفعك أكثر في نهاية المطاف كمهندس؟",
        "options": [
            {"id": "eng_q10_a", "text_en": "Excitement and stimulation — a career full of novel engineering challenges keeps me engaged",
             "text_ar": "الإثارة والتحفيز — مسيرة مليئة بالتحديات الهندسية الجديدة تبقيني متفاعلاً", "roles": ["mechanical", "electrical"]},
            {"id": "eng_q10_b", "text_en": "Seeking equilibrium — a meaningful engineering career that still leaves room for personal life",
             "text_ar": "السعي للتوازن — مسيرة هندسية ذات معنى لا تزال تترك مجالاً للحياة الشخصية", "roles": ["civil", "industrial"]},
            {"id": "eng_q10_c", "text_en": "To excel in my engineering field above all — I want to be known as the best at what I do",
             "text_ar": "التفوق في مجالي الهندسي قبل كل شيء — أريد أن أُعرف بأنني الأفضل فيما أفعله", "roles": ["mechanical", "electrical"]},
            {"id": "eng_q10_d", "text_en": "Being considered dependable and loyal — building a long, steady career with an organization I believe in",
             "text_ar": "أن أُعتبر موثوقاً وأميناً — بناء مسيرة مهنية طويلة ومستقرة مع منظمة أؤمن بها", "roles": ["civil", "industrial"]},
            {"id": "eng_q10_e", "text_en": "Advancing and being recognized as a leader — rising to manage major engineering programs",
             "text_ar": "التقدم والاعتراف بي كقائد — الصعود لإدارة برامج هندسية كبرى", "roles": ["eng_coord", "industrial"]},
        ],
    },
]

_QUESTIONS_BIZ: list[dict] = [
    {
        "id": "biz_q1",
        "text_en": "Which business activity sounds most interesting to you?",
        "text_ar": "أي نشاط تجاري يبدو الأكثر إثارةً لاهتمامك؟",
        "options": [
            {"id": "biz_q1_a", "text_en": "Analyzing financial data and building forecasting models",
             "text_ar": "تحليل البيانات المالية وبناء نماذج التنبؤ", "roles": ["financial"]},
            {"id": "biz_q1_b", "text_en": "Understanding customer behavior and creating marketing campaigns",
             "text_ar": "فهم سلوك العملاء وإنشاء الحملات التسويقية", "roles": ["marketing"]},
            {"id": "biz_q1_c", "text_en": "Managing projects, timelines, and cross-functional teams",
             "text_ar": "إدارة المشاريع والجداول الزمنية والفرق متعددة الوظائف", "roles": ["biz_coord"]},
            {"id": "biz_q1_d", "text_en": "Mapping and improving core business processes",
             "text_ar": "رسم وتحسين العمليات التجارية الأساسية", "roles": ["biz_analyst", "operations"]},
            {"id": "biz_q1_e", "text_en": "Recruiting, developing, and retaining great talent",
             "text_ar": "استقطاب المواهب المتميزة وتطويرها والاحتفاظ بها", "roles": ["hr"]},
        ],
    },
    {
        "id": "biz_q2",
        "text_en": "What type of business problem do you enjoy solving most?",
        "text_ar": "ما نوع مشكلة الأعمال التي تستمتع بحلها أكثر؟",
        "options": [
            {"id": "biz_q2_a", "text_en": "\"Why are our profits declining and how do we fix it?\"",
             "text_ar": "«لماذا تنخفض أرباحنا وكيف نصلح ذلك؟»", "roles": ["financial"]},
            {"id": "biz_q2_b", "text_en": "\"How do we attract and retain more customers?\"",
             "text_ar": "«كيف نجذب المزيد من العملاء ونحتفظ بهم؟»", "roles": ["marketing"]},
            {"id": "biz_q2_c", "text_en": "\"How do we deliver this initiative on time and budget?\"",
             "text_ar": "«كيف نسلم هذه المبادرة في الوقت المحدد وضمن الميزانية؟»", "roles": ["biz_coord"]},
            {"id": "biz_q2_d", "text_en": "\"Why is this process slow and how do we streamline it?\"",
             "text_ar": "«لماذا هذه العملية بطيئة وكيف نبسطها؟»", "roles": ["biz_analyst", "operations"]},
            {"id": "biz_q2_e", "text_en": "\"How do we build a stronger, more engaged team?\"",
             "text_ar": "«كيف نبني فريقاً أقوى وأكثر تفاعلاً؟»", "roles": ["hr"]},
        ],
    },
    {
        "id": "biz_q3",
        "text_en": "Which academic subject excites you most?",
        "text_ar": "أي موضوع دراسي يثير اهتمامك أكثر؟",
        "options": [
            {"id": "biz_q3_a", "text_en": "Accounting, investment analysis, or financial markets",
             "text_ar": "المحاسبة أو تحليل الاستثمار أو الأسواق المالية", "roles": ["financial"]},
            {"id": "biz_q3_b", "text_en": "Marketing strategy, consumer behavior, or brand management",
             "text_ar": "استراتيجية التسويق أو سلوك المستهلك أو إدارة العلامة التجارية", "roles": ["marketing"]},
            {"id": "biz_q3_c", "text_en": "Project management, strategic planning, or agile methodologies",
             "text_ar": "إدارة المشاريع أو التخطيط الاستراتيجي أو الأساليب الرشيقة", "roles": ["biz_coord"]},
            {"id": "biz_q3_d", "text_en": "Operations management, process improvement, or systems thinking",
             "text_ar": "إدارة العمليات أو تحسين العمليات أو التفكير المنظومي", "roles": ["biz_analyst", "operations"]},
            {"id": "biz_q3_e", "text_en": "Organizational behavior, talent management, or leadership",
             "text_ar": "السلوك التنظيمي أو إدارة المواهب أو القيادة", "roles": ["hr"]},
        ],
    },
    {
        "id": "biz_q4",
        "text_en": "How do you feel about working with numbers and financial data?",
        "text_ar": "كيف تشعر حيال العمل مع الأرقام والبيانات المالية؟",
        "options": [
            {"id": "biz_q4_a", "text_en": "I love it — financial models and numbers are my strength",
             "text_ar": "أحبه — النماذج المالية والأرقام هي نقطة قوتي", "roles": ["financial"]},
            {"id": "biz_q4_b", "text_en": "I use it mainly to measure marketing performance and ROI",
             "text_ar": "أستخدمه بشكل رئيسي لقياس الأداء التسويقي وعائد الاستثمار", "roles": ["marketing"]},
            {"id": "biz_q4_c", "text_en": "I use it mainly for project budget and schedule tracking",
             "text_ar": "أستخدمه بشكل رئيسي لتتبع ميزانية المشروع والجدول الزمني", "roles": ["biz_coord"]},
            {"id": "biz_q4_d", "text_en": "I analyze it to find process gaps and improvement opportunities",
             "text_ar": "أحلله لإيجاد ثغرات العمليات وفرص التحسين", "roles": ["biz_analyst", "operations"]},
            {"id": "biz_q4_e", "text_en": "I prefer working with people — numbers are secondary to me",
             "text_ar": "أفضل العمل مع الناس — الأرقام ثانوية بالنسبة لي", "roles": ["hr", "marketing"]},
        ],
    },
    {
        "id": "biz_q5",
        "text_en": "What kind of output would you be most proud to deliver?",
        "text_ar": "ما نوع المخرجات التي ستكون أكثر فخراً بتسليمها؟",
        "options": [
            {"id": "biz_q5_a", "text_en": "A financial model, valuation report, or investment recommendation",
             "text_ar": "نموذج مالي أو تقرير تقييم أو توصية استثمارية", "roles": ["financial"]},
            {"id": "biz_q5_b", "text_en": "A marketing campaign that significantly grows revenue and brand awareness",
             "text_ar": "حملة تسويقية تزيد الإيرادات والوعي بالعلامة التجارية بشكل ملحوظ", "roles": ["marketing"]},
            {"id": "biz_q5_c", "text_en": "A major project delivered on time, within scope and budget",
             "text_ar": "مشروع رئيسي يُسلَّم في الوقت المحدد وضمن النطاق والميزانية", "roles": ["biz_coord"]},
            {"id": "biz_q5_d", "text_en": "A redesigned business process that saves the company significant time and cost",
             "text_ar": "عملية تجارية مُعاد تصميمها توفر الوقت والتكلفة للشركة بشكل ملحوظ", "roles": ["biz_analyst", "operations"]},
            {"id": "biz_q5_e", "text_en": "A talent program that measurably improves employee engagement and retention",
             "text_ar": "برنامج مواهب يحسن بشكل قابل للقياس تفاعل الموظفين والاحتفاظ بهم", "roles": ["hr"]},
        ],
    },
    {
        "id": "biz_q6",
        "text_en": "Which role would you most want to shadow for a week?",
        "text_ar": "أي دور تريد مرافقته لمدة أسبوع أكثر؟",
        "options": [
            {"id": "biz_q6_a", "text_en": "A Financial Analyst building a company valuation model",
             "text_ar": "محلل مالي يبني نموذج تقييم شركة", "roles": ["financial"]},
            {"id": "biz_q6_b", "text_en": "A Marketing Manager launching a major product campaign",
             "text_ar": "مدير تسويق يطلق حملة منتج رئيسية", "roles": ["marketing"]},
            {"id": "biz_q6_c", "text_en": "A Project Manager running a high-stakes business initiative",
             "text_ar": "مدير مشروع يدير مبادرة تجارية عالية المخاطر", "roles": ["biz_coord"]},
            {"id": "biz_q6_d", "text_en": "A Business Analyst redesigning a company's core workflow",
             "text_ar": "محلل أعمال يُعيد تصميم سير عمل أساسي للشركة", "roles": ["biz_analyst"]},
            {"id": "biz_q6_e", "text_en": "An HR Business Partner shaping the company's talent strategy",
             "text_ar": "شريك أعمال HR يشكّل استراتيجية المواهب في الشركة", "roles": ["hr"]},
        ],
    },
    # ── Adapted from CSM Q21 (center of influence vs long-term valued employee) + Q6 (troubleshooter vs leader)
    {
        "id": "biz_q7",
        "text_en": "Which business career path feels most like you?",
        "text_ar": "أي مسار مهني في الأعمال يشبهك أكثر؟",
        "options": [
            {"id": "biz_q7_a", "text_en": "I want to be at the center of influence — advancing into leadership and driving major decisions",
             "text_ar": "أريد أن أكون في مركز التأثير — التقدم نحو القيادة وقيادة القرارات الكبرى", "roles": ["financial", "biz_coord"]},
            {"id": "biz_q7_b", "text_en": "I want to be the trusted expert in my function — valued for my deep knowledge and reliability",
             "text_ar": "أريد أن أكون الخبير الموثوق في وظيفتي — موضع تقدير لمعرفتي العميقة وموثوقيتي", "roles": ["biz_analyst", "operations"]},
            {"id": "biz_q7_c", "text_en": "I enjoy being the 'trouble-shooter' — energized by exciting high-impact campaigns or business challenges",
             "text_ar": "أستمتع بأن أكون 'حل المشكلات' — تشحنني الحملات المثيرة عالية التأثير أو تحديات الأعمال", "roles": ["marketing", "biz_coord"]},
            {"id": "biz_q7_d", "text_en": "I want long-term employment — to be valued, belong, and make steady contributions to a stable team",
             "text_ar": "أريد عملاً طويل الأمد — أن أُقدَّر وأنتمي وأقدم إسهامات ثابتة لفريق مستقر", "roles": ["hr", "operations"]},
            {"id": "biz_q7_e", "text_en": "I want maximum autonomy — consulting, working independently, or setting my own direction",
             "text_ar": "أريد أقصى قدر من الاستقلالية — استشارات أو عمل مستقل أو تحديد اتجاهي الخاص", "roles": ["biz_analyst", "financial"]},
        ],
    },
    # ── Adapted from CSM Q26 (financial success/power vs work-life balance) + Q28 (long-term team vs fast-paced project)
    {
        "id": "biz_q8",
        "text_en": "What does career success look like to you in business?",
        "text_ar": "كيف يبدو النجاح المهني بالنسبة لك في عالم الأعمال؟",
        "options": [
            {"id": "biz_q8_a", "text_en": "Financial success, increased power, and rising prestige within an organization",
             "text_ar": "النجاح المالي والقوة المتزايدة والمكانة المتصاعدة داخل المنظمة", "roles": ["financial", "biz_coord"]},
            {"id": "biz_q8_b", "text_en": "A meaningful career that doesn't consume my personal life — balance between work, family, and self",
             "text_ar": "مسيرة مهنية ذات معنى لا تستهلك حياتي الشخصية — توازن بين العمل والأسرة والذات", "roles": ["hr", "operations"]},
            {"id": "biz_q8_c", "text_en": "Being a recognized expert — continuous professional development and mastery of my field",
             "text_ar": "أن أُعترف بي كخبير — التطوير المهني المستمر وإتقان مجالي", "roles": ["biz_analyst", "financial"]},
            {"id": "biz_q8_d", "text_en": "The thrill of fast-paced projects, high-impact campaigns, and exciting wins",
             "text_ar": "إثارة المشاريع السريعة والحملات عالية التأثير والانتصارات المثيرة", "roles": ["marketing", "biz_coord"]},
            {"id": "biz_q8_e", "text_en": "Stability, appreciation, and a secure place in an organization with a team I trust",
             "text_ar": "الاستقرار والتقدير ومكانة آمنة في منظمة مع فريق أثق به", "roles": ["hr", "operations", "biz_analyst"]},
        ],
    },

    # ── Adapted from CSM Q9 (competent/loyal/trustworthy vs politically skillful/leader) + Q14 (stable/tenacious vs independent/self-directed)
    {
        "id": "biz_q9",
        "text_en": "Which best describes your professional identity in business?",
        "text_ar": "أيٌّ من هذه الخيارات يصف هويتك المهنية في الأعمال؟",
        "options": [
            {"id": "biz_q9_a", "text_en": "I am competent, loyal, and trustworthy — the reliable backbone of any business team",
             "text_ar": "أنا كفء وأمين وموثوق — العمود الفقري الموثوق لأي فريق أعمال", "roles": ["hr", "operations"]},
            {"id": "biz_q9_b", "text_en": "I am politically skillful and a strong communicator — I lead teams and win stakeholder buy-in",
             "text_ar": "أنا ماهر سياسياً ومتواصل قوي — أقود الفرق وأكسب دعم أصحاب المصلحة", "roles": ["biz_coord", "marketing"]},
            {"id": "biz_q9_c", "text_en": "I am stable and tenacious — I stay the course and deliver consistently even under pressure",
             "text_ar": "أنا مستقر وثابت العزم — أثبت على المسار وأسلّم باستمرار حتى تحت الضغط", "roles": ["operations", "biz_analyst"]},
            {"id": "biz_q9_d", "text_en": "I am independent and self-directed — I develop my career along my own interests and set my own direction",
             "text_ar": "أنا مستقل وأقود نفسي — أطور مسيرتي المهنية وفق اهتماماتي وأحدد اتجاهي الخاص", "roles": ["financial", "biz_analyst"]},
            {"id": "biz_q9_e", "text_en": "I am analytical and strategic — I turn data and business insight into measurable organizational impact",
             "text_ar": "أنا تحليلي واستراتيجي — أحوّل البيانات ورؤى الأعمال إلى أثر تنظيمي قابل للقياس", "roles": ["financial", "biz_analyst"]},
        ],
    },
    # ── Adapted from CSM Q30 (equilibrium vs excitement/stimulation) + Q2 (leisure/relationships vs subordinating personal needs for advancement)
    {
        "id": "biz_q10",
        "text_en": "What drives you most in your business career?",
        "text_ar": "ما الذي يحفّزك أكثر في مسيرتك في الأعمال؟",
        "options": [
            {"id": "biz_q10_a", "text_en": "Excitement and stimulation — fast-moving environments, high-stakes decisions, and exciting wins",
             "text_ar": "الإثارة والتحفيز — بيئات سريعة الوتيرة وقرارات عالية المخاطر وانتصارات مثيرة", "roles": ["marketing", "biz_coord"]},
            {"id": "biz_q10_b", "text_en": "Seeking equilibrium — a fulfilling business career that doesn't consume my personal and family life",
             "text_ar": "السعي للتوازن — مسيرة أعمال مُشبِعة لا تستهلك حياتي الشخصية والعائلية", "roles": ["hr", "operations"]},
            {"id": "biz_q10_c", "text_en": "Advancing up the organization — I will subordinate personal needs when needed to reach the top",
             "text_ar": "الصعود في المنظمة — سأتنازل عن الاحتياجات الشخصية عند الحاجة للوصول إلى القمة", "roles": ["biz_coord", "financial"]},
            {"id": "biz_q10_d", "text_en": "Becoming a recognized expert in my field — professional mastery matters more than titles or power",
             "text_ar": "أن أصبح خبيراً معترفاً به في مجالي — الإتقان المهني يهمني أكثر من المسميات أو السلطة", "roles": ["biz_analyst", "financial"]},
            {"id": "biz_q10_e", "text_en": "Making a lasting positive difference to the people in my organization and the teams I support",
             "text_ar": "إحداث فرق إيجابي دائم في حياة الناس في منظمتي والفرق التي أدعمها", "roles": ["hr", "operations"]},
        ],
    },
]

_QUESTIONS_BY_MAJOR: dict[str, list[dict]] = {
    "it":  _QUESTIONS_IT,
    "eng": _QUESTIONS_ENG,
    "biz": _QUESTIONS_BIZ,
}

_OPTION_ROLES: dict[str, list[str]] = {
    opt["id"]: opt["roles"]
    for bank in _QUESTIONS_BY_MAJOR.values()
    for q in bank
    for opt in q["options"]
}

_MAJOR_ROLES: dict[str, list[str]] = {
    "it":  ["software_dev", "data_analyst", "cybersecurity", "cloud_network",
            "it_support", "systems_analyst", "biz_analyst_it"],
    "eng": ["mechanical", "electrical", "civil", "industrial", "eng_coord"],
    "biz": ["financial", "marketing", "biz_coord", "biz_analyst", "operations", "hr"],
}


def _max_possible(major: str) -> int:
    return len(_QUESTIONS_BY_MAJOR.get(major, []))


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SurveyAnswer(BaseModel):
    question_id: str
    option_id: str


class SurveySubmit(BaseModel):
    selected_major: MajorKey
    answers: list[SurveyAnswer]


class SurveyRoleResult(BaseModel):
    id: str | None = None
    role_key: str
    name_en: str
    name_ar: str
    description: str | None = None
    explanation_en: str
    explanation_ar: str
    score: int
    max_score: int
    match_percent: int


class SurveyResult(BaseModel):
    selected_major: str
    selected_major_label: str
    selected_major_icon: str
    top_roles: list[SurveyRoleResult]   # exactly 3
    score_breakdown: dict[str, int]     # role_key → raw score


# ── GET /career/role-survey/majors ────────────────────────────────────────────

@router.get("/majors")
def get_majors():
    """Return the three allowed majors. No auth required."""
    return {"majors": _MAJORS}


# ── GET /career/role-survey/questions ────────────────────────────────────────

@router.get("/questions")
def get_questions(
    major: MajorKey = Query(..., description="Major key: it | eng | biz"),
):
    """Return the question bank for the requested major. No auth required."""
    questions = _QUESTIONS_BY_MAJOR.get(major)
    if not questions:
        raise HTTPException(status_code=404, detail=f"Unknown major: '{major}'")
    return {"major": major, "questions": questions, "total": len(questions)}


# ── POST /career/role-survey/submit ──────────────────────────────────────────

@router.post("/submit", response_model=SurveyResult)
def submit_survey(
    body: SurveySubmit,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Score answers within the selected major, return top-3 role suggestions.
    Each answer awards 1 point per role_key in that option's `roles` list.
    Roles are cross-referenced with the DB catalog for real IDs + descriptions.
    """
    major = body.selected_major
    questions_for_major = _QUESTIONS_BY_MAJOR.get(major)
    if not questions_for_major:
        raise HTTPException(status_code=422, detail=f"Unknown major: '{major}'")
    if not body.answers:
        raise HTTPException(status_code=400, detail="No answers provided.")

    # ── Score ─────────────────────────────────────────────────────────────
    scores: dict[str, int] = {rk: 0 for rk in _MAJOR_ROLES[major]}
    seen: set[str] = set()
    valid_q_ids = {q["id"] for q in questions_for_major}

    for ans in body.answers:
        if ans.question_id not in valid_q_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Question '{ans.question_id}' does not belong to major '{major}'",
            )
        if ans.question_id in seen:
            raise HTTPException(
                status_code=422,
                detail=f"Duplicate answer for '{ans.question_id}'",
            )
        if ans.option_id not in _OPTION_ROLES:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown option_id: '{ans.option_id}'",
            )
        seen.add(ans.question_id)
        for rk in _OPTION_ROLES[ans.option_id]:
            if rk in scores:
                scores[rk] += 1

    # ── Top 3 ─────────────────────────────────────────────────────────────
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top3_keys = [rk for rk, _ in ranked[:3]]
    max_score = _max_possible(major)

    # ── DB cross-reference ────────────────────────────────────────────────
    # Search ALL leaf roles globally so we find roles that live under a
    # different field in the DB (e.g. "Systems Analyst" is under Business
    # in the seed data but is suggested for IT users).
    major_info = _MAJOR_BY_KEY[major]
    db_roles_by_name: dict[str, Role] = {}
    try:
        all_leaf_roles = (
            db.query(Role)
            .filter(Role.role_type == "role")
            .all()
        )
        for r in all_leaf_roles:
            db_roles_by_name[r.name_en.lower()] = r
    except Exception:
        pass  # gracefully degrade — roles will have id=None

    # ── Build result ──────────────────────────────────────────────────────
    top_roles: list[SurveyRoleResult] = []
    for rk in top3_keys:
        raw = scores[rk]
        name_en = _ROLE_NAMES[rk]["en"]
        db_match = db_roles_by_name.get(name_en.lower())
        top_roles.append(
            SurveyRoleResult(
                id=str(db_match.id) if db_match else None,
                role_key=rk,
                name_en=name_en,
                name_ar=_ROLE_NAMES[rk]["ar"],
                description=db_match.description if db_match else None,
                explanation_en=_ROLE_EXPLANATIONS.get(rk, {}).get("en", ""),
                explanation_ar=_ROLE_EXPLANATIONS.get(rk, {}).get("ar", ""),
                score=raw,
                max_score=max_score,
                match_percent=min(100, round(raw / max_score * 100)) if max_score else 0,
            )
        )

    return SurveyResult(
        selected_major=major,
        selected_major_label=major_info["label_en"],
        selected_major_icon=major_info["icon"],
        top_roles=top_roles,
        score_breakdown=scores,
    )