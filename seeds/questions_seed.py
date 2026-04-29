"""
Seed script for interview questions.

Usage:
    python -m app.seeds.questions

Populates the questions table with:
  - 15 technical + 15 behavioral questions per role (parent & child)
  - 15 general interview questions (role_name="general")
All bilingual (EN + AR). Safe to re-run — uses get_or_create.
"""
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.question import Question


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


# ────────────────────────────────────────────
#  GENERAL QUESTIONS (role_name = "general")
# ────────────────────────────────────────────

GENERAL_QUESTIONS = [
    {
        "en": "What are your biggest strengths?",
        "ar": "ما هي أبرز نقاط قوتك؟",
        "difficulty": 1,
    },
    {
        "en": "What are your biggest weaknesses?",
        "ar": "ما هي أبرز نقاط ضعفك؟",
        "difficulty": 1,
    },
    {
        "en": "Why are you interested in this position?",
        "ar": "لماذا أنت مهتم بهذه الوظيفة؟",
        "difficulty": 1,
    },
    {
        "en": "Where do you see yourself in five years?",
        "ar": "أين ترى نفسك بعد خمس سنوات؟",
        "difficulty": 2,
    },
    {
        "en": "Why are you leaving your current job?",
        "ar": "لماذا تريد ترك وظيفتك الحالية؟",
        "difficulty": 2,
    },
    {
        "en": "What motivates you to do your best work?",
        "ar": "ما الذي يحفزك لتقديم أفضل ما لديك في العمل؟",
        "difficulty": 2,
    },
    {
        "en": "How do you handle stress and pressure?",
        "ar": "كيف تتعامل مع الضغط والتوتر في العمل؟",
        "difficulty": 2,
    },
    {
        "en": "What is your expected salary range?",
        "ar": "ما هو نطاق الراتب المتوقع لديك؟",
        "difficulty": 2,
    },
    {
        "en": "Describe a challenging situation you faced and how you overcame it.",
        "ar": "صف موقفاً صعباً واجهته وكيف تغلبت عليه.",
        "difficulty": 3,
    },
    {
        "en": "What do you know about our company?",
        "ar": "ماذا تعرف عن شركتنا؟",
        "difficulty": 1,
    },
    {
        "en": "How do you prioritize your tasks when you have multiple deadlines?",
        "ar": "كيف ترتب أولويات مهامك عندما يكون لديك عدة مواعيد نهائية؟",
        "difficulty": 2,
    },
    {
        "en": "What makes you the best candidate for this role?",
        "ar": "ما الذي يجعلك أفضل مرشح لهذا الدور؟",
        "difficulty": 3,
    },
    {
        "en": "Do you prefer working independently or as part of a team?",
        "ar": "هل تفضل العمل بشكل مستقل أم كجزء من فريق؟",
        "difficulty": 1,
    },
    {
        "en": "How do you stay current with industry trends and developments?",
        "ar": "كيف تبقى مطلعاً على أحدث التطورات والاتجاهات في مجالك؟",
        "difficulty": 2,
    },
    {
        "en": "Do you have any questions for us?",
        "ar": "هل لديك أي أسئلة لنا؟",
        "difficulty": 1,
    },
]


# ────────────────────────────────────────────
#  ROLE-SPECIFIC QUESTIONS
#  Each role has "technical" and "behavioral" lists
#  Each question: (en, ar, difficulty)
# ────────────────────────────────────────────

ROLE_QUESTIONS: dict[str, dict[str, list[tuple[str, str, int]]]] = {

    # ══════════════════════════════════════════
    #  SOFTWARE ENGINEERING (Parent)
    # ══════════════════════════════════════════
    "Software Engineering": {
        "technical": [
            ("What is the difference between compiled and interpreted languages?", "ما الفرق بين اللغات المُترجمة (compiled) واللغات المُفسَّرة (interpreted)؟", 1),
            ("Explain the concept of Object-Oriented Programming and its four pillars.", "اشرح مفهوم البرمجة كائنية التوجه وأركانها الأربعة.", 2),
            ("What are design patterns and why are they important?", "ما هي أنماط التصميم (Design Patterns) ولماذا هي مهمة؟", 3),
            ("Explain the difference between SQL and NoSQL databases.", "اشرح الفرق بين قواعد البيانات العلائقية (SQL) وغير العلائقية (NoSQL).", 2),
            ("What is version control and why is Git widely used?", "ما هو نظام التحكم بالإصدارات ولماذا يُستخدم Git على نطاق واسع؟", 1),
            ("Describe the software development life cycle (SDLC).", "صف دورة حياة تطوير البرمجيات (SDLC).", 2),
            ("What is the difference between REST and GraphQL APIs?", "ما الفرق بين واجهات REST و GraphQL؟", 3),
            ("Explain the SOLID principles in software design.", "اشرح مبادئ SOLID في تصميم البرمجيات.", 3),
            ("What are microservices and how do they differ from monolithic architecture?", "ما هي الخدمات المصغرة (Microservices) وكيف تختلف عن البنية المتراصة (Monolithic)؟", 3),
            ("What is the purpose of unit testing and integration testing?", "ما الغرض من اختبار الوحدات واختبار التكامل؟", 2),
            ("Explain the concept of CI/CD and its benefits.", "اشرح مفهوم التكامل والنشر المستمر (CI/CD) وفوائده.", 2),
            ("What is technical debt and how should it be managed?", "ما هو الدين التقني وكيف يجب إدارته؟", 3),
            ("Describe the difference between concurrency and parallelism.", "صف الفرق بين التزامن (Concurrency) والتوازي (Parallelism).", 4),
            ("What are the main principles of clean code?", "ما هي المبادئ الأساسية للكود النظيف (Clean Code)؟", 2),
            ("Explain the concept of caching and when to use it.", "اشرح مفهوم التخزين المؤقت (Caching) ومتى يُستخدم.", 3),
        ],
        "behavioral": [
            ("Tell me about a time you had to learn a new technology quickly for a project.", "أخبرني عن موقف اضطررت فيه لتعلم تقنية جديدة بسرعة لمشروع ما.", 2),
            ("Describe a situation where you disagreed with a technical decision made by your team.", "صف موقفاً اختلفت فيه مع قرار تقني اتخذه فريقك.", 3),
            ("How do you handle a situation where project requirements change frequently?", "كيف تتعامل مع موقف تتغير فيه متطلبات المشروع بشكل متكرر؟", 2),
            ("Tell me about a time you had to debug a particularly difficult issue.", "أخبرني عن موقف اضطررت فيه لتصحيح خطأ برمجي صعب بشكل خاص.", 3),
            ("Describe how you mentor or help junior developers.", "صف كيف تقوم بتوجيه أو مساعدة المطورين المبتدئين.", 2),
            ("How do you balance code quality with delivery speed?", "كيف توازن بين جودة الكود وسرعة التسليم؟", 3),
            ("Tell me about a project you are most proud of and why.", "أخبرني عن مشروع تفتخر به أكثر ولماذا.", 2),
            ("How do you handle receiving critical feedback on your code during a code review?", "كيف تتعامل مع تلقي ملاحظات نقدية على كودك أثناء مراجعة الكود؟", 2),
            ("Describe a time when you had to work with a difficult teammate.", "صف موقفاً اضطررت فيه للعمل مع زميل صعب المراس.", 3),
            ("How do you stay updated with the latest technologies and trends?", "كيف تبقى مطلعاً على أحدث التقنيات والاتجاهات؟", 1),
            ("Tell me about a time you had to make a trade-off between two technical approaches.", "أخبرني عن موقف اضطررت فيه للمفاضلة بين نهجين تقنيين.", 3),
            ("How do you handle tight deadlines on software projects?", "كيف تتعامل مع المواعيد النهائية الضيقة في مشاريع البرمجيات؟", 2),
            ("Describe a time you took initiative to improve a process or system.", "صف موقفاً بادرت فيه بتحسين عملية أو نظام.", 2),
            ("How do you communicate technical concepts to non-technical stakeholders?", "كيف تشرح المفاهيم التقنية لأصحاب المصلحة غير التقنيين؟", 3),
            ("Tell me about a time you failed in a project and what you learned from it.", "أخبرني عن موقف فشلت فيه في مشروع وماذا تعلمت منه.", 3),
        ],
    },

    # ──────────────────────────────────────────
    #  Backend Developer
    # ──────────────────────────────────────────
    "Backend Developer": {
        "technical": [
            ("Explain the difference between SQL joins: INNER, LEFT, RIGHT, and FULL.", "اشرح الفرق بين أنواع الربط في SQL: INNER و LEFT و RIGHT و FULL.", 2),
            ("What is an ORM and what are its advantages and disadvantages?", "ما هو ORM وما هي مزاياه وعيوبه؟", 2),
            ("How do you design a RESTful API? What best practices do you follow?", "كيف تصمم واجهة RESTful API؟ ما أفضل الممارسات التي تتبعها؟", 3),
            ("Explain database indexing and when you would use it.", "اشرح فهرسة قواعد البيانات ومتى تستخدمها.", 3),
            ("What is the N+1 query problem and how do you solve it?", "ما هي مشكلة N+1 في الاستعلامات وكيف تحلها؟", 3),
            ("Describe how authentication and authorization work in a backend system.", "صف كيف تعمل المصادقة والتفويض في نظام الخادم.", 3),
            ("What is middleware and how is it used in web frameworks?", "ما هو الـ Middleware وكيف يُستخدم في أطر العمل؟", 2),
            ("Explain the concept of database migrations and why they are important.", "اشرح مفهوم ترحيل قواعد البيانات (Migrations) ولماذا هي مهمة.", 2),
            ("What strategies do you use for API rate limiting?", "ما الاستراتيجيات التي تستخدمها لتحديد معدل الطلبات على الـ API؟", 3),
            ("How do you handle error handling and logging in backend applications?", "كيف تتعامل مع معالجة الأخطاء والتسجيل (Logging) في تطبيقات الخادم؟", 2),
            ("What is connection pooling and why is it important?", "ما هو تجميع الاتصالات (Connection Pooling) ولماذا هو مهم؟", 3),
            ("Explain the difference between synchronous and asynchronous processing.", "اشرح الفرق بين المعالجة المتزامنة وغير المتزامنة.", 2),
            ("How would you design a system to handle millions of requests per day?", "كيف تصمم نظاماً يتعامل مع ملايين الطلبات يومياً؟", 4),
            ("What is message queuing and when would you use tools like RabbitMQ or Kafka?", "ما هو نظام طوابير الرسائل ومتى تستخدم أدوات مثل RabbitMQ أو Kafka؟", 4),
            ("Explain database normalization and its different forms.", "اشرح تطبيع قواعد البيانات (Normalization) وأشكاله المختلفة.", 3),
        ],
        "behavioral": [
            ("Tell me about a time you optimized a slow API endpoint.", "أخبرني عن موقف قمت فيه بتحسين نقطة نهاية API بطيئة.", 3),
            ("Describe a production outage you handled and the lessons learned.", "صف عطلاً في بيئة الإنتاج تعاملت معه والدروس المستفادة.", 3),
            ("How do you prioritize which bugs to fix first?", "كيف ترتب أولويات الأخطاء البرمجية التي يجب إصلاحها أولاً؟", 2),
            ("Tell me about a time you had to refactor legacy code.", "أخبرني عن موقف اضطررت فيه لإعادة هيكلة كود قديم.", 3),
            ("How do you ensure the security of the systems you build?", "كيف تضمن أمان الأنظمة التي تبنيها؟", 2),
            ("Describe a situation where you had to choose between multiple database solutions.", "صف موقفاً اضطررت فيه للاختيار بين عدة حلول لقواعد البيانات.", 3),
            ("How do you approach writing documentation for your APIs?", "كيف تتعامل مع كتابة التوثيق لواجهات الـ API الخاصة بك؟", 2),
            ("Tell me about a time you collaborated closely with frontend developers.", "أخبرني عن موقف تعاونت فيه بشكل وثيق مع مطوري الواجهة الأمامية.", 2),
            ("How do you handle disagreements about architectural decisions?", "كيف تتعامل مع الخلافات حول القرارات المعمارية؟", 3),
            ("Describe a time when you had to work under pressure to fix a critical bug.", "صف موقفاً اضطررت فيه للعمل تحت ضغط لإصلاح خطأ حرج.", 2),
            ("How do you ensure your code is maintainable for other developers?", "كيف تضمن أن يكون كودك قابلاً للصيانة من قبل مطورين آخرين؟", 2),
            ("Tell me about a time you improved the performance of a database query.", "أخبرني عن موقف قمت فيه بتحسين أداء استعلام قاعدة بيانات.", 3),
            ("How do you handle on-call responsibilities and incident response?", "كيف تتعامل مع مسؤوليات المناوبة والاستجابة للحوادث؟", 2),
            ("Describe a time you introduced a new tool or technology to your team.", "صف موقفاً قدمت فيه أداة أو تقنية جديدة لفريقك.", 2),
            ("How do you balance building new features with maintaining existing systems?", "كيف توازن بين بناء ميزات جديدة وصيانة الأنظمة الحالية؟", 3),
        ],
    },

    # ──────────────────────────────────────────
    #  Frontend Developer
    # ──────────────────────────────────────────
    "Frontend Developer": {
        "technical": [
            ("What is the virtual DOM and how does it improve performance?", "ما هو الـ Virtual DOM وكيف يحسن الأداء؟", 2),
            ("Explain the difference between CSS Flexbox and Grid.", "اشرح الفرق بين CSS Flexbox و Grid.", 2),
            ("What is responsive design and how do you implement it?", "ما هو التصميم المتجاوب وكيف تطبقه؟", 1),
            ("Explain the concept of state management in React.", "اشرح مفهوم إدارة الحالة (State Management) في React.", 3),
            ("What are Web Accessibility standards and why do they matter?", "ما هي معايير إمكانية الوصول على الويب ولماذا هي مهمة؟", 2),
            ("Explain the difference between SSR, SSG, and CSR.", "اشرح الفرق بين SSR و SSG و CSR.", 3),
            ("What are React hooks and how do useState and useEffect work?", "ما هي React Hooks وكيف يعمل useState و useEffect؟", 2),
            ("How do you optimize the performance of a web application?", "كيف تحسن أداء تطبيق الويب؟", 3),
            ("What is Cross-Origin Resource Sharing (CORS) and how do you handle it?", "ما هو CORS وكيف تتعامل معه؟", 2),
            ("Explain the concept of component lifecycle in React.", "اشرح مفهوم دورة حياة المكون في React.", 2),
            ("What is lazy loading and how does it improve performance?", "ما هو التحميل الكسول (Lazy Loading) وكيف يحسن الأداء؟", 2),
            ("How do you handle form validation on the frontend?", "كيف تتعامل مع التحقق من صحة النماذج في الواجهة الأمامية؟", 2),
            ("What are Progressive Web Apps (PWAs) and their key features?", "ما هي تطبيقات الويب التقدمية (PWAs) وميزاتها الرئيسية؟", 3),
            ("Explain the difference between localStorage, sessionStorage, and cookies.", "اشرح الفرق بين localStorage و sessionStorage و cookies.", 2),
            ("What are micro-frontends and when would you use them?", "ما هي الواجهات الأمامية المصغرة (Micro-frontends) ومتى تستخدمها؟", 4),
        ],
        "behavioral": [
            ("Tell me about a time you improved the user experience of a web application.", "أخبرني عن موقف قمت فيه بتحسين تجربة المستخدم لتطبيق ويب.", 2),
            ("How do you handle cross-browser compatibility issues?", "كيف تتعامل مع مشاكل التوافق بين المتصفحات؟", 2),
            ("Describe a time you had to work closely with a designer to implement a complex UI.", "صف موقفاً اضطررت فيه للعمل بشكل وثيق مع مصمم لتنفيذ واجهة مستخدم معقدة.", 3),
            ("How do you approach debugging a CSS layout issue?", "كيف تتعامل مع تصحيح مشكلة في تخطيط CSS؟", 2),
            ("Tell me about a time you advocated for better accessibility in a project.", "أخبرني عن موقف دافعت فيه عن تحسين إمكانية الوصول في مشروع.", 2),
            ("How do you keep up with the rapidly changing frontend ecosystem?", "كيف تواكب النظام البيئي المتغير بسرعة للواجهات الأمامية؟", 1),
            ("Describe a situation where you had to balance design requirements with technical constraints.", "صف موقفاً اضطررت فيه للموازنة بين متطلبات التصميم والقيود التقنية.", 3),
            ("Tell me about a performance bottleneck you identified and resolved in a frontend app.", "أخبرني عن عنق زجاجة في الأداء اكتشفته وحللته في تطبيق واجهة أمامية.", 3),
            ("How do you handle conflicting feedback from multiple stakeholders on UI design?", "كيف تتعامل مع ملاحظات متعارضة من عدة أطراف حول تصميم الواجهة؟", 3),
            ("Describe a time you had to migrate a frontend application to a new framework.", "صف موقفاً اضطررت فيه لنقل تطبيق واجهة أمامية إلى إطار عمل جديد.", 3),
            ("How do you ensure code consistency in a large frontend codebase?", "كيف تضمن اتساق الكود في قاعدة كود واجهة أمامية كبيرة؟", 2),
            ("Tell me about a time you had to deliver a pixel-perfect implementation.", "أخبرني عن موقف اضطررت فيه لتنفيذ تصميم مطابق تماماً للمطلوب.", 2),
            ("How do you handle technical debt in frontend projects?", "كيف تتعامل مع الدين التقني في مشاريع الواجهة الأمامية؟", 3),
            ("Describe how you collaborate with backend developers on API integration.", "صف كيف تتعاون مع مطوري الخادم في تكامل الـ API.", 2),
            ("Tell me about a time you simplified a complex user interface.", "أخبرني عن موقف قمت فيه بتبسيط واجهة مستخدم معقدة.", 2),
        ],
    },

    # ──────────────────────────────────────────
    #  Full-Stack Developer
    # ──────────────────────────────────────────
    "Full-Stack Developer": {
        "technical": [
            ("How do you decide which logic belongs on the frontend versus the backend?", "كيف تقرر أي المنطق يجب أن يكون في الواجهة الأمامية مقابل الخادم؟", 3),
            ("Explain how you would set up a full-stack application from scratch.", "اشرح كيف تنشئ تطبيقاً متكاملاً من الصفر.", 2),
            ("What is the role of an API gateway in a full-stack architecture?", "ما هو دور بوابة الـ API في بنية التطبيق المتكامل؟", 3),
            ("How do you manage shared types or contracts between frontend and backend?", "كيف تدير الأنواع أو العقود المشتركة بين الواجهة الأمامية والخادم؟", 3),
            ("Explain how WebSockets work and when you would use them over REST.", "اشرح كيف تعمل WebSockets ومتى تستخدمها بدلاً من REST.", 3),
            ("How do you handle authentication across a full-stack application?", "كيف تتعامل مع المصادقة عبر تطبيق متكامل؟", 3),
            ("What tools do you use for end-to-end testing in full-stack apps?", "ما الأدوات التي تستخدمها لاختبار التطبيق المتكامل من البداية إلى النهاية؟", 2),
            ("Explain the concept of server-side rendering and its benefits.", "اشرح مفهوم العرض من جانب الخادم (SSR) وفوائده.", 3),
            ("How do you deploy a full-stack application to production?", "كيف تنشر تطبيقاً متكاملاً في بيئة الإنتاج؟", 2),
            ("What is containerization and how does Docker help in full-stack development?", "ما هي الحاويات (Containerization) وكيف يساعد Docker في التطوير المتكامل؟", 2),
            ("How do you handle file uploads across frontend and backend?", "كيف تتعامل مع رفع الملفات عبر الواجهة الأمامية والخادم؟", 2),
            ("Explain how you would implement real-time notifications in a web app.", "اشرح كيف تنفذ الإشعارات الفورية في تطبيق ويب.", 3),
            ("What are environment variables and how do you manage them across environments?", "ما هي متغيرات البيئة وكيف تديرها عبر بيئات مختلفة؟", 2),
            ("How do you handle database schema changes in a running application?", "كيف تتعامل مع تغييرات مخطط قاعدة البيانات في تطبيق قيد التشغيل؟", 3),
            ("What is a monorepo and what are its pros and cons for full-stack projects?", "ما هو الـ Monorepo وما إيجابياته وسلبياته لمشاريع التطبيقات المتكاملة؟", 3),
        ],
        "behavioral": [
            ("How do you decide when to specialize versus stay generalist?", "كيف تقرر متى تتخصص مقابل البقاء كمطور شامل؟", 2),
            ("Tell me about a time you had to context-switch between frontend and backend tasks.", "أخبرني عن موقف اضطررت فيه للتنقل بين مهام الواجهة الأمامية والخادم.", 2),
            ("Describe a full-stack project where you owned the entire feature end-to-end.", "صف مشروعاً متكاملاً كنت مسؤولاً فيه عن ميزة كاملة من البداية إلى النهاية.", 3),
            ("How do you manage your time when responsible for both frontend and backend?", "كيف تدير وقتك عندما تكون مسؤولاً عن الواجهة الأمامية والخادم معاً؟", 2),
            ("Tell me about a time a full-stack decision you made impacted both sides negatively.", "أخبرني عن قرار متكامل اتخذته أثر سلباً على كلا الجانبين.", 3),
            ("How do you handle situations where you lack expertise in one layer of the stack?", "كيف تتعامل مع مواقف تفتقر فيها للخبرة في طبقة معينة من التطبيق؟", 2),
            ("Describe how you ensure quality when you're the sole developer on a project.", "صف كيف تضمن الجودة عندما تكون المطور الوحيد في مشروع.", 3),
            ("Tell me about a time you helped bridge communication between frontend and backend teams.", "أخبرني عن موقف ساعدت فيه في تسهيل التواصل بين فرق الواجهة الأمامية والخادم.", 2),
            ("How do you approach estimating work for a full-stack feature?", "كيف تقدّر حجم العمل لميزة متكاملة؟", 2),
            ("Describe a situation where you had to quickly learn a new technology to complete a task.", "صف موقفاً اضطررت فيه لتعلم تقنية جديدة بسرعة لإنجاز مهمة.", 2),
            ("How do you handle code reviews when you understand both sides of the application?", "كيف تتعامل مع مراجعات الكود عندما تفهم كلا جانبي التطبيق؟", 2),
            ("Tell me about a time you had to make a tough trade-off in system design.", "أخبرني عن موقف اضطررت فيه لاتخاذ مفاضلة صعبة في تصميم النظام.", 3),
            ("How do you ensure security across the entire stack?", "كيف تضمن الأمان عبر جميع طبقات التطبيق؟", 3),
            ("Describe a time you successfully shipped a feature under a tight deadline.", "صف موقفاً نجحت فيه بإطلاق ميزة ضمن موعد نهائي ضيق.", 2),
            ("How do you handle burnout when wearing multiple hats on a project?", "كيف تتعامل مع الإرهاق عندما تتحمل أدواراً متعددة في مشروع؟", 2),
        ],
    },

    # ──────────────────────────────────────────
    #  Mobile App Developer
    # ──────────────────────────────────────────
    "Mobile App Developer": {
        "technical": [
            ("What is the difference between native and cross-platform mobile development?", "ما الفرق بين تطوير التطبيقات الأصلية والمتعددة المنصات؟", 1),
            ("Explain the widget tree in Flutter.", "اشرح شجرة الـ Widgets في Flutter.", 2),
            ("What is the difference between StatefulWidget and StatelessWidget in Flutter?", "ما الفرق بين StatefulWidget و StatelessWidget في Flutter؟", 2),
            ("How do you manage state in a mobile application?", "كيف تدير الحالة (State) في تطبيق جوال؟", 3),
            ("What are the different ways to store data locally on a mobile device?", "ما هي الطرق المختلفة لتخزين البيانات محلياً على الجهاز المحمول؟", 2),
            ("Explain push notifications and how they work on iOS and Android.", "اشرح الإشعارات المباشرة وكيف تعمل على iOS و Android.", 3),
            ("How do you handle different screen sizes and resolutions?", "كيف تتعامل مع أحجام ودقة الشاشات المختلفة؟", 2),
            ("What is the app lifecycle on Android vs iOS?", "ما هي دورة حياة التطبيق على Android مقابل iOS؟", 3),
            ("How do you optimize battery consumption in a mobile app?", "كيف تحسن استهلاك البطارية في تطبيق جوال؟", 3),
            ("Explain how you would implement offline-first functionality.", "اشرح كيف تنفذ وظيفة العمل دون اتصال أولاً (Offline-first).", 3),
            ("What are platform channels in Flutter and when do you use them?", "ما هي قنوات المنصة (Platform Channels) في Flutter ومتى تستخدمها؟", 3),
            ("How do you handle deep linking in mobile apps?", "كيف تتعامل مع الروابط العميقة (Deep Linking) في تطبيقات الجوال؟", 3),
            ("What is the difference between Firebase Realtime Database and Firestore?", "ما الفرق بين Firebase Realtime Database و Firestore؟", 2),
            ("How do you secure API keys and sensitive data in a mobile app?", "كيف تؤمن مفاتيح الـ API والبيانات الحساسة في تطبيق جوال؟", 3),
            ("Explain the app store submission and review process.", "اشرح عملية تقديم ومراجعة التطبيق في متجر التطبيقات.", 2),
        ],
        "behavioral": [
            ("Tell me about a time you had to fix a critical bug reported by users in production.", "أخبرني عن موقف اضطررت فيه لإصلاح خطأ حرج أبلغ عنه المستخدمون في الإنتاج.", 3),
            ("How do you handle negative app store reviews?", "كيف تتعامل مع التقييمات السلبية في متجر التطبيقات؟", 2),
            ("Describe a time you had to support multiple platforms with limited resources.", "صف موقفاً اضطررت فيه لدعم منصات متعددة بموارد محدودة.", 3),
            ("How do you decide between building a feature natively vs using a package?", "كيف تقرر بين بناء ميزة أصلياً أو استخدام حزمة جاهزة؟", 2),
            ("Tell me about a time you improved app performance significantly.", "أخبرني عن موقف حسنت فيه أداء التطبيق بشكل كبير.", 3),
            ("How do you approach testing on different devices and OS versions?", "كيف تتعامل مع الاختبار على أجهزة وإصدارات أنظمة تشغيل مختلفة؟", 2),
            ("Describe a situation where you had to balance user experience with technical limitations.", "صف موقفاً اضطررت فيه للموازنة بين تجربة المستخدم والقيود التقنية.", 3),
            ("How do you gather and incorporate user feedback into your development process?", "كيف تجمع ملاحظات المستخدمين وتدمجها في عملية التطوير؟", 2),
            ("Tell me about a challenging UI animation you implemented.", "أخبرني عن رسوم متحركة معقدة في واجهة المستخدم قمت بتنفيذها.", 3),
            ("How do you manage app releases and versioning?", "كيف تدير إصدارات التطبيق وتحديثاته؟", 2),
            ("Describe a time you had to work with a backend team to resolve an integration issue.", "صف موقفاً اضطررت فيه للعمل مع فريق الخادم لحل مشكلة تكامل.", 2),
            ("How do you handle scope creep in mobile app projects?", "كيف تتعامل مع زحف النطاق في مشاريع تطبيقات الجوال؟", 2),
            ("Tell me about a time you had to reject an app store submission and how you resolved it.", "أخبرني عن موقف تم فيه رفض تطبيقك من متجر التطبيقات وكيف حللت المشكلة.", 3),
            ("How do you stay current with mobile development trends?", "كيف تبقى مطلعاً على اتجاهات تطوير تطبيقات الجوال؟", 1),
            ("Describe a time you successfully reduced the app size or load time.", "صف موقفاً نجحت فيه بتقليل حجم التطبيق أو وقت التحميل.", 3),
        ],
    },

    # ──────────────────────────────────────────
    #  DevOps Engineer
    # ──────────────────────────────────────────
    "DevOps Engineer": {
        "technical": [
            ("Explain the concept of Infrastructure as Code (IaC).", "اشرح مفهوم البنية التحتية ككود (IaC).", 2),
            ("What is the difference between Docker containers and virtual machines?", "ما الفرق بين حاويات Docker والأجهزة الافتراضية؟", 2),
            ("Describe a typical CI/CD pipeline and its stages.", "صف خط أنابيب CI/CD نموذجي ومراحله.", 2),
            ("What is Kubernetes and how does it orchestrate containers?", "ما هو Kubernetes وكيف ينسق الحاويات؟", 3),
            ("Explain the difference between blue-green and canary deployments.", "اشرح الفرق بين النشر الأزرق-الأخضر ونشر الكناري.", 3),
            ("How do you monitor and alert on production systems?", "كيف تراقب أنظمة الإنتاج وتعد التنبيهات؟", 3),
            ("What is Terraform and how does it differ from Ansible?", "ما هو Terraform وكيف يختلف عن Ansible؟", 3),
            ("Explain the concept of immutable infrastructure.", "اشرح مفهوم البنية التحتية غير القابلة للتغيير (Immutable Infrastructure).", 3),
            ("How do you manage secrets and credentials in a DevOps environment?", "كيف تدير الأسرار وبيانات الاعتماد في بيئة DevOps؟", 3),
            ("What is a service mesh and when would you use one?", "ما هو شبكة الخدمات (Service Mesh) ومتى تستخدمها؟", 4),
            ("Explain how you would set up auto-scaling for a web application.", "اشرح كيف تعد التوسع التلقائي لتطبيق ويب.", 3),
            ("What is GitOps and how does it work?", "ما هو GitOps وكيف يعمل؟", 3),
            ("How do you implement disaster recovery in cloud environments?", "كيف تنفذ التعافي من الكوارث في البيئات السحابية؟", 4),
            ("Explain the 12-factor app methodology.", "اشرح منهجية التطبيق ذي الاثني عشر عاملاً (12-Factor App).", 3),
            ("What are the key metrics you monitor in a production environment?", "ما هي المقاييس الرئيسية التي تراقبها في بيئة الإنتاج؟", 2),
        ],
        "behavioral": [
            ("Tell me about a time you automated a manual process that saved significant time.", "أخبرني عن موقف قمت فيه بأتمتة عملية يدوية وفرت وقتاً كبيراً.", 2),
            ("Describe a major production incident you handled and your post-mortem process.", "صف حادثة إنتاج كبيرة تعاملت معها وعملية تحليل ما بعد الحادث.", 3),
            ("How do you convince developers to adopt DevOps practices?", "كيف تقنع المطورين بتبني ممارسات DevOps؟", 2),
            ("Tell me about a time you improved deployment frequency.", "أخبرني عن موقف قمت فيه بتحسين تكرار النشر.", 3),
            ("How do you balance stability with speed of deployment?", "كيف توازن بين الاستقرار وسرعة النشر؟", 3),
            ("Describe a situation where you had to troubleshoot a complex infrastructure issue.", "صف موقفاً اضطررت فيه لاستكشاف مشكلة بنية تحتية معقدة وإصلاحها.", 3),
            ("How do you handle on-call rotations and prevent alert fatigue?", "كيف تتعامل مع جداول المناوبة وتمنع إرهاق التنبيهات؟", 2),
            ("Tell me about a time you reduced infrastructure costs significantly.", "أخبرني عن موقف قللت فيه تكاليف البنية التحتية بشكل كبير.", 3),
            ("How do you ensure security in your CI/CD pipelines?", "كيف تضمن الأمان في خطوط أنابيب CI/CD الخاصة بك؟", 3),
            ("Describe a time you had to migrate a system with zero downtime.", "صف موقفاً اضطررت فيه لترحيل نظام بدون توقف.", 4),
            ("How do you document infrastructure and share knowledge with your team?", "كيف توثق البنية التحتية وتشارك المعرفة مع فريقك؟", 2),
            ("Tell me about a time you implemented monitoring that prevented a future outage.", "أخبرني عن موقف نفذت فيه مراقبة منعت عطلاً مستقبلياً.", 3),
            ("How do you handle resistance to change when introducing new tools?", "كيف تتعامل مع مقاومة التغيير عند تقديم أدوات جديدة؟", 2),
            ("Describe a time you had to scale infrastructure rapidly due to unexpected traffic.", "صف موقفاً اضطررت فيه لتوسيع البنية التحتية بسرعة بسبب حركة مرور غير متوقعة.", 3),
            ("How do you approach learning new DevOps tools and technologies?", "كيف تتعامل مع تعلم أدوات وتقنيات DevOps جديدة؟", 1),
        ],
    },

    # ──────────────────────────────────────────
    #  QA / Test Engineer
    # ──────────────────────────────────────────
    "QA / Test Engineer": {
        "technical": [
            ("What is the difference between manual testing and automated testing?", "ما الفرق بين الاختبار اليدوي والاختبار الآلي؟", 1),
            ("Explain the testing pyramid and its layers.", "اشرح هرم الاختبار وطبقاته.", 2),
            ("What is regression testing and when should it be performed?", "ما هو اختبار الانحدار ومتى يجب إجراؤه؟", 2),
            ("Describe the difference between black-box and white-box testing.", "صف الفرق بين اختبار الصندوق الأسود والصندوق الأبيض.", 2),
            ("What tools do you use for automated testing and why?", "ما الأدوات التي تستخدمها للاختبار الآلي ولماذا؟", 2),
            ("How do you write effective test cases?", "كيف تكتب حالات اختبار فعالة؟", 2),
            ("What is performance testing and what tools do you use?", "ما هو اختبار الأداء وما الأدوات التي تستخدمها؟", 3),
            ("Explain the concept of test-driven development (TDD).", "اشرح مفهوم التطوير المدفوع بالاختبار (TDD).", 3),
            ("How do you test APIs and what do you verify?", "كيف تختبر واجهات الـ API وماذا تتحقق منه؟", 2),
            ("What is boundary value analysis in testing?", "ما هو تحليل القيم الحدية في الاختبار؟", 2),
            ("How do you integrate testing into a CI/CD pipeline?", "كيف تدمج الاختبار في خط أنابيب CI/CD؟", 3),
            ("What is the difference between smoke testing and sanity testing?", "ما الفرق بين اختبار الدخان واختبار السلامة؟", 2),
            ("How do you handle flaky tests?", "كيف تتعامل مع الاختبارات غير المستقرة (Flaky Tests)؟", 3),
            ("What is code coverage and how important is it?", "ما هي تغطية الكود وما مدى أهميتها؟", 2),
            ("Explain the concept of shift-left testing.", "اشرح مفهوم الاختبار المبكر (Shift-left Testing).", 3),
        ],
        "behavioral": [
            ("Tell me about a bug you found that no one else could reproduce.", "أخبرني عن خطأ اكتشفته لم يتمكن أحد آخر من إعادة إنتاجه.", 3),
            ("How do you prioritize testing when time is limited?", "كيف ترتب أولويات الاختبار عندما يكون الوقت محدوداً؟", 2),
            ("Describe a time you pushed back on releasing a feature due to quality concerns.", "صف موقفاً رفضت فيه إصدار ميزة بسبب مخاوف تتعلق بالجودة.", 3),
            ("How do you communicate bugs to developers without causing friction?", "كيف تبلغ المطورين عن الأخطاء دون إحداث احتكاك؟", 2),
            ("Tell me about a time you improved the testing process in your team.", "أخبرني عن موقف حسنت فيه عملية الاختبار في فريقك.", 2),
            ("How do you handle disagreements with developers about whether something is a bug?", "كيف تتعامل مع الخلافات مع المطورين حول ما إذا كان شيء ما خطأ برمجياً؟", 3),
            ("Describe a time when you missed a critical bug and what you learned.", "صف موقفاً فاتك فيه خطأ حرج وماذا تعلمت.", 3),
            ("How do you maintain test documentation and keep it up to date?", "كيف تحافظ على توثيق الاختبارات وتبقيه محدثاً؟", 2),
            ("Tell me about a time you advocated for automation in your testing workflow.", "أخبرني عن موقف دافعت فيه عن الأتمتة في سير عمل الاختبار.", 2),
            ("How do you handle testing in an agile environment with fast iterations?", "كيف تتعامل مع الاختبار في بيئة أجايل مع تكرارات سريعة؟", 2),
            ("Describe a situation where you found a security vulnerability during testing.", "صف موقفاً اكتشفت فيه ثغرة أمنية أثناء الاختبار.", 3),
            ("How do you build relationships with developers as a QA engineer?", "كيف تبني علاقات مع المطورين كمهندس ضمان جودة؟", 2),
            ("Tell me about a time you tested a feature with incomplete requirements.", "أخبرني عن موقف اختبرت فيه ميزة بمتطلبات غير مكتملة.", 2),
            ("How do you measure the effectiveness of your testing efforts?", "كيف تقيس فعالية جهود الاختبار الخاصة بك؟", 3),
            ("Describe how you adapt your testing strategy for different types of projects.", "صف كيف تكيف استراتيجية الاختبار لأنواع مختلفة من المشاريع.", 2),
        ],
    },

    # ══════════════════════════════════════════
    #  DATA & AI (Parent)
    # ══════════════════════════════════════════
    "Data & AI": {
        "technical": [
            ("What is the difference between supervised and unsupervised learning?", "ما الفرق بين التعلم الخاضع للإشراف والتعلم غير الخاضع للإشراف؟", 2),
            ("Explain the bias-variance tradeoff.", "اشرح المفاضلة بين التحيز والتباين (Bias-Variance Tradeoff).", 3),
            ("What is a data pipeline and what are its key components?", "ما هو خط أنابيب البيانات وما مكوناته الرئيسية؟", 2),
            ("Explain the difference between batch and stream processing.", "اشرح الفرق بين المعالجة الدفعية والمعالجة المتدفقة.", 3),
            ("What is feature engineering and why is it important?", "ما هي هندسة الميزات (Feature Engineering) ولماذا هي مهمة؟", 3),
            ("Explain overfitting and how to prevent it.", "اشرح الإفراط في التخصيص (Overfitting) وكيفية منعه.", 2),
            ("What is the difference between a data lake and a data warehouse?", "ما الفرق بين بحيرة البيانات ومستودع البيانات؟", 2),
            ("Explain cross-validation and its purpose.", "اشرح التحقق المتقاطع (Cross-validation) والغرض منه.", 2),
            ("What are the main types of neural network architectures?", "ما هي الأنواع الرئيسية لبنى الشبكات العصبية؟", 3),
            ("How do you handle missing data in a dataset?", "كيف تتعامل مع البيانات المفقودة في مجموعة بيانات؟", 2),
            ("What is the difference between precision and recall?", "ما الفرق بين الدقة (Precision) والاستدعاء (Recall)؟", 2),
            ("Explain the concept of dimensionality reduction.", "اشرح مفهوم تقليل الأبعاد (Dimensionality Reduction).", 3),
            ("What is transfer learning and when is it useful?", "ما هو التعلم بالنقل (Transfer Learning) ومتى يكون مفيداً؟", 3),
            ("How do you evaluate the performance of a machine learning model?", "كيف تقيم أداء نموذج التعلم الآلي؟", 2),
            ("What are embeddings and how are they used in NLP?", "ما هي التضمينات (Embeddings) وكيف تُستخدم في معالجة اللغة الطبيعية؟", 3),
        ],
        "behavioral": [
            ("Tell me about a time you had to explain complex data findings to a non-technical audience.", "أخبرني عن موقف اضطررت فيه لشرح نتائج بيانات معقدة لجمهور غير تقني.", 2),
            ("Describe a project where data quality was a major challenge.", "صف مشروعاً كانت فيه جودة البيانات تحدياً كبيراً.", 3),
            ("How do you handle situations where data contradicts stakeholder expectations?", "كيف تتعامل مع مواقف تتناقض فيها البيانات مع توقعات أصحاب المصلحة؟", 3),
            ("Tell me about a time your model did not perform as expected in production.", "أخبرني عن موقف لم يؤدِ فيه نموذجك كما هو متوقع في الإنتاج.", 3),
            ("How do you prioritize which data problems to solve first?", "كيف ترتب أولويات مشاكل البيانات التي يجب حلها أولاً؟", 2),
            ("Describe a time you had to work with messy or unstructured data.", "صف موقفاً اضطررت فيه للعمل مع بيانات فوضوية أو غير منظمة.", 2),
            ("How do you ensure ethical use of data and AI in your projects?", "كيف تضمن الاستخدام الأخلاقي للبيانات والذكاء الاصطناعي في مشاريعك؟", 3),
            ("Tell me about a time you had to balance model accuracy with interpretability.", "أخبرني عن موقف اضطررت فيه للموازنة بين دقة النموذج وقابليته للتفسير.", 3),
            ("How do you collaborate with engineers to deploy data solutions?", "كيف تتعاون مع المهندسين لنشر حلول البيانات؟", 2),
            ("Describe a data project where you had to iterate significantly before reaching a good result.", "صف مشروع بيانات اضطررت فيه للتكرار بشكل كبير قبل الوصول لنتيجة جيدة.", 3),
            ("How do you handle tight deadlines on data projects?", "كيف تتعامل مع المواعيد النهائية الضيقة في مشاريع البيانات؟", 2),
            ("Tell me about a time you discovered a bias in your data or model.", "أخبرني عن موقف اكتشفت فيه تحيزاً في بياناتك أو نموذجك.", 3),
            ("How do you communicate uncertainty in your data analyses?", "كيف تنقل عدم اليقين في تحليلات البيانات الخاصة بك؟", 2),
            ("Describe how you stay updated with the fast-moving AI field.", "صف كيف تبقى محدثاً في مجال الذكاء الاصطناعي سريع التطور.", 1),
            ("Tell me about a time you had to make a recommendation based on limited data.", "أخبرني عن موقف اضطررت فيه لتقديم توصية بناءً على بيانات محدودة.", 3),
        ],
    },

    # ──────────────────────────────────────────
    #  Data Analyst
    # ──────────────────────────────────────────
    "Data Analyst": {
        "technical": [
            ("What is the difference between OLTP and OLAP systems?", "ما الفرق بين أنظمة OLTP و OLAP؟", 2),
            ("How do you write a SQL query to find the second highest salary?", "كيف تكتب استعلام SQL لإيجاد ثاني أعلى راتب؟", 2),
            ("What are window functions in SQL and give an example use case.", "ما هي دوال النافذة (Window Functions) في SQL مع مثال على استخدامها.", 3),
            ("Explain the difference between correlation and causation.", "اشرح الفرق بين الارتباط والسببية.", 2),
            ("What is a pivot table and how do you create one?", "ما هو الجدول المحوري (Pivot Table) وكيف تنشئ واحداً؟", 1),
            ("How do you handle outliers in your data analysis?", "كيف تتعامل مع القيم الشاذة في تحليل البيانات؟", 2),
            ("What are the different types of data visualizations and when to use each?", "ما هي أنواع تصورات البيانات المختلفة ومتى تستخدم كل نوع؟", 2),
            ("Explain the concept of A/B testing.", "اشرح مفهوم اختبار A/B.", 3),
            ("How do you calculate and interpret a confidence interval?", "كيف تحسب وتفسر فترة الثقة (Confidence Interval)؟", 3),
            ("What is data normalization and why is it important in analysis?", "ما هو تطبيع البيانات ولماذا هو مهم في التحليل؟", 2),
            ("How do you connect to and query a database from Python?", "كيف تتصل بقاعدة بيانات وتستعلم منها باستخدام Python؟", 2),
            ("What is the difference between measures and dimensions in BI tools?", "ما الفرق بين المقاييس والأبعاد في أدوات الذكاء التجاري؟", 2),
            ("How do you create a dashboard that tells a compelling data story?", "كيف تنشئ لوحة معلومات تحكي قصة بيانات مقنعة؟", 3),
            ("What are common data cleaning techniques you use?", "ما هي تقنيات تنظيف البيانات الشائعة التي تستخدمها؟", 2),
            ("Explain the difference between descriptive, diagnostic, predictive, and prescriptive analytics.", "اشرح الفرق بين التحليلات الوصفية والتشخيصية والتنبؤية والتوجيهية.", 3),
        ],
        "behavioral": [
            ("Tell me about a time your analysis led to a significant business decision.", "أخبرني عن موقف أدى فيه تحليلك إلى قرار أعمال مهم.", 3),
            ("How do you handle requests for data that doesn't exist or is unreliable?", "كيف تتعامل مع طلبات للبيانات غير الموجودة أو غير الموثوقة؟", 2),
            ("Describe a time you had to present data findings that stakeholders didn't want to hear.", "صف موقفاً اضطررت فيه لعرض نتائج بيانات لم يرغب أصحاب المصلحة في سماعها.", 3),
            ("How do you prioritize multiple data requests from different teams?", "كيف ترتب أولويات طلبات البيانات المتعددة من فرق مختلفة؟", 2),
            ("Tell me about a time you identified a data quality issue that affected reporting.", "أخبرني عن موقف حددت فيه مشكلة جودة بيانات أثرت على التقارير.", 3),
            ("How do you ensure your analyses are reproducible?", "كيف تضمن أن تحليلاتك قابلة للتكرار؟", 2),
            ("Describe a time you had to simplify a complex dataset for a non-technical audience.", "صف موقفاً اضطررت فيه لتبسيط مجموعة بيانات معقدة لجمهور غير تقني.", 2),
            ("How do you handle ambiguous analysis requests?", "كيف تتعامل مع طلبات التحليل الغامضة؟", 2),
            ("Tell me about a time you automated a reporting process.", "أخبرني عن موقف قمت فيه بأتمتة عملية إعداد التقارير.", 2),
            ("How do you validate the accuracy of your data before presenting it?", "كيف تتحقق من دقة بياناتك قبل تقديمها؟", 2),
            ("Describe a situation where you had to work with incomplete data.", "صف موقفاً اضطررت فيه للعمل مع بيانات غير مكتملة.", 2),
            ("How do you handle competing interpretations of the same data?", "كيف تتعامل مع تفسيرات متنافسة لنفس البيانات؟", 3),
            ("Tell me about a time you went beyond the original request to provide deeper insights.", "أخبرني عن موقف تجاوزت فيه الطلب الأصلي لتقديم رؤى أعمق.", 2),
            ("How do you manage stakeholder expectations about what data can and cannot answer?", "كيف تدير توقعات أصحاب المصلحة حول ما يمكن وما لا يمكن للبيانات الإجابة عليه؟", 3),
            ("Describe how you approach learning a new BI tool or data technology.", "صف كيف تتعامل مع تعلم أداة ذكاء تجاري أو تقنية بيانات جديدة.", 1),
        ],
    },

    # ──────────────────────────────────────────
    #  Data Engineer
    # ──────────────────────────────────────────
    "Data Engineer": {
        "technical": [
            ("What is the difference between ETL and ELT?", "ما الفرق بين ETL و ELT؟", 2),
            ("Explain the concept of data partitioning and its benefits.", "اشرح مفهوم تقسيم البيانات (Partitioning) وفوائده.", 3),
            ("How does Apache Spark handle distributed data processing?", "كيف يتعامل Apache Spark مع معالجة البيانات الموزعة؟", 3),
            ("What is schema-on-read versus schema-on-write?", "ما الفرق بين المخطط عند القراءة والمخطط عند الكتابة؟", 3),
            ("How do you ensure data quality in a data pipeline?", "كيف تضمن جودة البيانات في خط أنابيب البيانات؟", 3),
            ("What is data lineage and why is it important?", "ما هو نسب البيانات (Data Lineage) ولماذا هو مهم؟", 2),
            ("Explain the concept of slowly changing dimensions (SCD).", "اشرح مفهوم الأبعاد المتغيرة ببطء (SCD).", 3),
            ("How do you handle late-arriving data in a streaming pipeline?", "كيف تتعامل مع البيانات المتأخرة في خط أنابيب متدفق؟", 4),
            ("What is a data catalog and what purpose does it serve?", "ما هو فهرس البيانات (Data Catalog) وما الغرض منه؟", 2),
            ("Explain the star schema and snowflake schema in data warehousing.", "اشرح مخطط النجمة ومخطط الندف الثلجي في مستودعات البيانات.", 3),
            ("How do you monitor and debug data pipeline failures?", "كيف تراقب وتصحح أعطال خط أنابيب البيانات؟", 3),
            ("What are the main considerations when choosing between batch and real-time processing?", "ما هي الاعتبارات الرئيسية عند الاختيار بين المعالجة الدفعية والفورية؟", 3),
            ("How do you handle data deduplication at scale?", "كيف تتعامل مع إزالة تكرار البيانات على نطاق واسع؟", 3),
            ("What is Apache Airflow and how do you use it for orchestration?", "ما هو Apache Airflow وكيف تستخدمه للتنسيق؟", 3),
            ("Explain the concept of data governance.", "اشرح مفهوم حوكمة البيانات (Data Governance).", 2),
        ],
        "behavioral": [
            ("Tell me about a time you designed a data pipeline from scratch.", "أخبرني عن موقف صممت فيه خط أنابيب بيانات من الصفر.", 3),
            ("Describe a data pipeline failure you resolved and what you learned.", "صف عطلاً في خط أنابيب بيانات قمت بحله وماذا تعلمت.", 3),
            ("How do you work with data scientists to understand their data needs?", "كيف تعمل مع علماء البيانات لفهم احتياجاتهم من البيانات؟", 2),
            ("Tell me about a time you improved the performance of a data pipeline.", "أخبرني عن موقف حسنت فيه أداء خط أنابيب بيانات.", 3),
            ("How do you handle conflicting data source requirements from different teams?", "كيف تتعامل مع متطلبات مصادر بيانات متعارضة من فرق مختلفة؟", 3),
            ("Describe a time you had to migrate data from one system to another.", "صف موقفاً اضطررت فيه لنقل بيانات من نظام إلى آخر.", 3),
            ("How do you ensure data security and privacy in your pipelines?", "كيف تضمن أمان البيانات والخصوصية في خطوط أنابيبك؟", 2),
            ("Tell me about a time you had to scale a system to handle significantly more data.", "أخبرني عن موقف اضطررت فيه لتوسيع نظام للتعامل مع بيانات أكثر بكثير.", 3),
            ("How do you document your data infrastructure?", "كيف توثق بنيتك التحتية للبيانات؟", 2),
            ("Describe a situation where you had to balance cost with data processing needs.", "صف موقفاً اضطررت فيه للموازنة بين التكلفة واحتياجات معالجة البيانات.", 3),
            ("How do you handle on-call responsibilities for data pipelines?", "كيف تتعامل مع مسؤوليات المناوبة لخطوط أنابيب البيانات؟", 2),
            ("Tell me about a time you introduced data quality checks that caught critical errors.", "أخبرني عن موقف أدخلت فيه فحوصات جودة بيانات اكتشفت أخطاء حرجة.", 3),
            ("How do you approach evaluating new data technologies?", "كيف تتعامل مع تقييم تقنيات بيانات جديدة؟", 2),
            ("Describe a time you collaborated with business stakeholders on data requirements.", "صف موقفاً تعاونت فيه مع أصحاب المصلحة في الأعمال حول متطلبات البيانات.", 2),
            ("How do you handle technical debt in data infrastructure?", "كيف تتعامل مع الدين التقني في البنية التحتية للبيانات؟", 3),
        ],
    },

    # ──────────────────────────────────────────
    #  Data Scientist
    # ──────────────────────────────────────────
    "Data Scientist": {
        "technical": [
            ("Explain the difference between classification and regression.", "اشرح الفرق بين التصنيف والانحدار.", 1),
            ("What is regularization and why is it used in machine learning?", "ما هو التنظيم (Regularization) ولماذا يُستخدم في التعلم الآلي؟", 3),
            ("How do you handle class imbalance in a classification problem?", "كيف تتعامل مع عدم توازن الفئات في مشكلة تصنيف؟", 3),
            ("Explain the difference between bagging and boosting.", "اشرح الفرق بين Bagging و Boosting.", 3),
            ("What is the curse of dimensionality?", "ما هي لعنة الأبعاد (Curse of Dimensionality)؟", 3),
            ("How do you select the right model for a given problem?", "كيف تختار النموذج المناسب لمشكلة معينة؟", 3),
            ("Explain hypothesis testing and p-values.", "اشرح اختبار الفرضيات وقيم p.", 2),
            ("What is the ROC curve and AUC score?", "ما هو منحنى ROC ودرجة AUC؟", 2),
            ("How do you perform feature selection?", "كيف تجري اختيار الميزات (Feature Selection)؟", 3),
            ("What is the difference between parametric and non-parametric models?", "ما الفرق بين النماذج البارامترية وغير البارامترية؟", 3),
            ("Explain how gradient descent works.", "اشرح كيف يعمل الانحدار التدريجي (Gradient Descent).", 3),
            ("What are ensemble methods and why are they effective?", "ما هي طرق التجميع (Ensemble Methods) ولماذا هي فعالة؟", 3),
            ("How do you interpret a confusion matrix?", "كيف تفسر مصفوفة الارتباك (Confusion Matrix)؟", 2),
            ("What is Bayesian inference and when would you use it?", "ما هو الاستدلال البايزي ومتى تستخدمه؟", 4),
            ("Explain the concept of model explainability and SHAP values.", "اشرح مفهوم قابلية تفسير النموذج وقيم SHAP.", 4),
        ],
        "behavioral": [
            ("Tell me about a data science project that had real business impact.", "أخبرني عن مشروع علم بيانات كان له تأثير حقيقي على الأعمال.", 3),
            ("How do you decide when a model is good enough to deploy?", "كيف تقرر متى يكون النموذج جيداً بما يكفي للنشر؟", 3),
            ("Describe a time you had to pivot your approach because initial results were poor.", "صف موقفاً اضطررت فيه لتغيير نهجك لأن النتائج الأولية كانت ضعيفة.", 3),
            ("How do you communicate model limitations to stakeholders?", "كيف تنقل قيود النموذج لأصحاب المصلحة؟", 2),
            ("Tell me about a time you had to choose between a simpler model and a more complex one.", "أخبرني عن موقف اضطررت فيه للاختيار بين نموذج أبسط وآخر أكثر تعقيداً.", 3),
            ("How do you handle situations where you have very limited data?", "كيف تتعامل مع مواقف لديك فيها بيانات محدودة جداً؟", 3),
            ("Describe how you stay current with new ML research and papers.", "صف كيف تبقى محدثاً مع أبحاث وأوراق التعلم الآلي الجديدة.", 1),
            ("Tell me about a time you had to work with a cross-functional team on a data project.", "أخبرني عن موقف اضطررت فيه للعمل مع فريق متعدد التخصصات في مشروع بيانات.", 2),
            ("How do you balance experimentation with delivering results on deadline?", "كيف توازن بين التجريب وتقديم النتائج في الموعد المحدد؟", 3),
            ("Describe a time your analysis revealed something unexpected.", "صف موقفاً كشف فيه تحليلك شيئاً غير متوقع.", 2),
            ("How do you approach reproducing results from a research paper?", "كيف تتعامل مع إعادة إنتاج نتائج من ورقة بحثية؟", 3),
            ("Tell me about a time you mentored someone in data science.", "أخبرني عن موقف قمت فيه بتوجيه شخص في علم البيانات.", 2),
            ("How do you handle ethical dilemmas in data science?", "كيف تتعامل مع المعضلات الأخلاقية في علم البيانات؟", 3),
            ("Describe a time you had to defend your methodology to skeptical stakeholders.", "صف موقفاً اضطررت فيه للدفاع عن منهجيتك أمام أصحاب مصلحة متشككين.", 3),
            ("How do you manage version control for data science experiments?", "كيف تدير التحكم في الإصدارات لتجارب علم البيانات؟", 2),
        ],
    },

    # ──────────────────────────────────────────
    #  Machine Learning Engineer
    # ──────────────────────────────────────────
    "Machine Learning Engineer": {
        "technical": [
            ("How do you deploy a machine learning model to production?", "كيف تنشر نموذج تعلم آلي في بيئة الإنتاج؟", 3),
            ("What is MLOps and why is it important?", "ما هو MLOps ولماذا هو مهم؟", 2),
            ("Explain the difference between online and offline model inference.", "اشرح الفرق بين الاستدلال عبر الإنترنت وغير المتصل للنماذج.", 3),
            ("How do you handle model versioning and experiment tracking?", "كيف تتعامل مع إصدارات النماذج وتتبع التجارب؟", 3),
            ("What is model drift and how do you detect it?", "ما هو انحراف النموذج (Model Drift) وكيف تكتشفه؟", 3),
            ("Explain the concept of model serving and its challenges.", "اشرح مفهوم خدمة النموذج (Model Serving) وتحدياته.", 3),
            ("How do you optimize model inference latency?", "كيف تحسن زمن استجابة استدلال النموذج؟", 4),
            ("What is quantization and how does it help in model deployment?", "ما هو التكميم (Quantization) وكيف يساعد في نشر النموذج؟", 4),
            ("How do you build a training pipeline that is reproducible?", "كيف تبني خط أنابيب تدريب قابل للتكرار؟", 3),
            ("What is A/B testing for ML models and how do you implement it?", "ما هو اختبار A/B لنماذج التعلم الآلي وكيف تنفذه؟", 3),
            ("Explain the concept of feature stores.", "اشرح مفهوم مخازن الميزات (Feature Stores).", 3),
            ("How do you handle large-scale distributed training?", "كيف تتعامل مع التدريب الموزع على نطاق واسع؟", 4),
            ("What is containerization's role in ML deployment?", "ما هو دور الحاويات في نشر التعلم الآلي؟", 2),
            ("How do you monitor ML models in production?", "كيف تراقب نماذج التعلم الآلي في الإنتاج؟", 3),
            ("Explain the difference between batch prediction and real-time prediction.", "اشرح الفرق بين التنبؤ الدفعي والتنبؤ الفوري.", 2),
        ],
        "behavioral": [
            ("Tell me about a time you deployed a model that failed in production.", "أخبرني عن موقف نشرت فيه نموذجاً فشل في الإنتاج.", 3),
            ("How do you balance research and engineering in your work?", "كيف توازن بين البحث والهندسة في عملك؟", 3),
            ("Describe a time you had to optimize a model for production constraints.", "صف موقفاً اضطررت فيه لتحسين نموذج ليناسب قيود الإنتاج.", 3),
            ("How do you collaborate with data scientists on model development?", "كيف تتعاون مع علماء البيانات في تطوير النماذج؟", 2),
            ("Tell me about a time you reduced model training costs.", "أخبرني عن موقف قللت فيه تكاليف تدريب النموذج.", 3),
            ("How do you handle the challenge of keeping models up-to-date?", "كيف تتعامل مع تحدي إبقاء النماذج محدثة؟", 2),
            ("Describe a situation where you had to choose between model accuracy and speed.", "صف موقفاً اضطررت فيه للاختيار بين دقة النموذج وسرعته.", 3),
            ("How do you ensure reproducibility in your ML experiments?", "كيف تضمن قابلية التكرار في تجارب التعلم الآلي الخاصة بك؟", 2),
            ("Tell me about a time you had to scale an ML system significantly.", "أخبرني عن موقف اضطررت فيه لتوسيع نظام تعلم آلي بشكل كبير.", 3),
            ("How do you handle disagreements about model architecture choices?", "كيف تتعامل مع الخلافات حول خيارات بنية النموذج؟", 2),
            ("Describe a time you automated part of the ML lifecycle.", "صف موقفاً قمت فيه بأتمتة جزء من دورة حياة التعلم الآلي.", 3),
            ("How do you stay current with the rapidly evolving ML ecosystem?", "كيف تبقى مطلعاً على النظام البيئي للتعلم الآلي المتطور بسرعة؟", 1),
            ("Tell me about a time you improved data preprocessing that led to better model performance.", "أخبرني عن موقف حسنت فيه معالجة البيانات الأولية مما أدى لأداء نموذج أفضل.", 3),
            ("How do you handle the pressure of deploying models that affect real users?", "كيف تتعامل مع ضغط نشر نماذج تؤثر على مستخدمين حقيقيين؟", 2),
            ("Describe how you document and share ML knowledge with your team.", "صف كيف توثق وتشارك معرفة التعلم الآلي مع فريقك.", 2),
        ],
    },

    # ──────────────────────────────────────────
    #  AI Research Engineer
    # ──────────────────────────────────────────
    "AI Research Engineer": {
        "technical": [
            ("Explain the transformer architecture and its key innovations.", "اشرح بنية المحول (Transformer) وابتكاراتها الرئيسية.", 4),
            ("What is the attention mechanism and how does it work?", "ما هي آلية الانتباه (Attention Mechanism) وكيف تعمل؟", 4),
            ("Explain the difference between GANs and VAEs.", "اشرح الفرق بين شبكات GAN و VAE.", 4),
            ("What is reinforcement learning and what are its main components?", "ما هو التعلم المعزز وما مكوناته الرئيسية؟", 3),
            ("How do you evaluate the quality of generated text or images?", "كيف تقيم جودة النصوص أو الصور المولدة؟", 3),
            ("Explain the concept of self-supervised learning.", "اشرح مفهوم التعلم الذاتي الإشراف.", 4),
            ("What are diffusion models and how do they work?", "ما هي نماذج الانتشار (Diffusion Models) وكيف تعمل؟", 4),
            ("How do you design experiments to validate a research hypothesis?", "كيف تصمم تجارب للتحقق من فرضية بحثية؟", 3),
            ("What is few-shot and zero-shot learning?", "ما هو التعلم بعدد قليل من الأمثلة والتعلم بدون أمثلة؟", 3),
            ("Explain the concept of knowledge distillation.", "اشرح مفهوم تقطير المعرفة (Knowledge Distillation).", 4),
            ("What are the current challenges in NLP research?", "ما هي التحديات الحالية في أبحاث معالجة اللغة الطبيعية؟", 3),
            ("How do you handle the reproducibility crisis in AI research?", "كيف تتعامل مع أزمة قابلية التكرار في أبحاث الذكاء الاصطناعي؟", 3),
            ("Explain contrastive learning and its applications.", "اشرح التعلم التبايني (Contrastive Learning) وتطبيقاته.", 4),
            ("What is neural architecture search (NAS)?", "ما هو البحث عن البنية العصبية (NAS)؟", 4),
            ("How do you scale training to very large datasets and models?", "كيف توسع التدريب لمجموعات بيانات ونماذج كبيرة جداً؟", 4),
        ],
        "behavioral": [
            ("Tell me about a research project that didn't go as planned.", "أخبرني عن مشروع بحثي لم يسر كما هو مخطط.", 3),
            ("How do you decide which research direction to pursue?", "كيف تقرر أي اتجاه بحثي تتبعه؟", 3),
            ("Describe a time you had to present your research findings to a broad audience.", "صف موقفاً اضطررت فيه لتقديم نتائج بحثك لجمهور واسع.", 2),
            ("How do you balance exploring new ideas with publishing results?", "كيف توازن بين استكشاف أفكار جديدة ونشر النتائج؟", 3),
            ("Tell me about a time you collaborated with researchers from different domains.", "أخبرني عن موقف تعاونت فيه مع باحثين من مجالات مختلفة.", 2),
            ("How do you handle negative results in your research?", "كيف تتعامل مع النتائج السلبية في بحثك؟", 2),
            ("Describe a time your research was criticized and how you responded.", "صف موقفاً تعرض فيه بحثك للنقد وكيف استجبت.", 3),
            ("How do you stay motivated during long research projects?", "كيف تحافظ على حماسك خلال مشاريع بحثية طويلة؟", 2),
            ("Tell me about a breakthrough moment in one of your research projects.", "أخبرني عن لحظة اختراق في أحد مشاريعك البحثية.", 2),
            ("How do you approach reading and reviewing academic papers?", "كيف تتعامل مع قراءة ومراجعة الأوراق الأكاديمية؟", 1),
            ("Describe how you mentor junior researchers.", "صف كيف توجه الباحثين المبتدئين.", 2),
            ("How do you bridge the gap between research and practical applications?", "كيف تسد الفجوة بين البحث والتطبيقات العملية؟", 3),
            ("Tell me about a time you had to abandon a promising research direction.", "أخبرني عن موقف اضطررت فيه للتخلي عن اتجاه بحثي واعد.", 3),
            ("How do you manage your time between reading, coding, and writing papers?", "كيف تدير وقتك بين القراءة والبرمجة وكتابة الأوراق؟", 2),
            ("Describe your approach to ethical AI research.", "صف نهجك في أبحاث الذكاء الاصطناعي الأخلاقية.", 2),
        ],
    },

    # ══════════════════════════════════════════
    #  CYBERSECURITY (Parent)
    # ══════════════════════════════════════════
    "Cybersecurity": {
        "technical": [
            ("What is the CIA triad in information security?", "ما هو مثلث CIA في أمن المعلومات؟", 1),
            ("Explain the difference between symmetric and asymmetric encryption.", "اشرح الفرق بين التشفير المتماثل وغير المتماثل.", 2),
            ("What is a firewall and what are the different types?", "ما هو جدار الحماية وما أنواعه المختلفة؟", 1),
            ("Explain the concept of defense in depth.", "اشرح مفهوم الدفاع في العمق (Defense in Depth).", 2),
            ("What is a zero-day vulnerability?", "ما هي ثغرة اليوم الصفري (Zero-day)؟", 2),
            ("Explain the difference between IDS and IPS.", "اشرح الفرق بين نظام كشف التسلل ونظام منع التسلل.", 2),
            ("What is multi-factor authentication and why is it important?", "ما هي المصادقة متعددة العوامل ولماذا هي مهمة؟", 1),
            ("Explain the OWASP Top 10 and its significance.", "اشرح قائمة OWASP العشر الأوائل وأهميتها.", 2),
            ("What is a VPN and how does it work?", "ما هي الشبكة الافتراضية الخاصة (VPN) وكيف تعمل؟", 2),
            ("Explain the concept of least privilege principle.", "اشرح مبدأ الحد الأدنى من الصلاحيات.", 2),
            ("What is social engineering and how can organizations protect against it?", "ما هي الهندسة الاجتماعية وكيف يمكن للمؤسسات الحماية منها؟", 2),
            ("Explain the difference between vulnerability scanning and penetration testing.", "اشرح الفرق بين فحص الثغرات واختبار الاختراق.", 2),
            ("What is PKI and how does it work?", "ما هي البنية التحتية للمفتاح العام (PKI) وكيف تعمل؟", 3),
            ("Explain the concept of security hardening.", "اشرح مفهوم تعزيز الأمان (Security Hardening).", 2),
            ("What is the difference between black-hat, white-hat, and grey-hat hackers?", "ما الفرق بين القراصنة ذوي القبعة السوداء والبيضاء والرمادية؟", 1),
        ],
        "behavioral": [
            ("Tell me about a security incident you helped resolve.", "أخبرني عن حادث أمني ساعدت في حله.", 3),
            ("How do you stay updated with the latest security threats?", "كيف تبقى مطلعاً على أحدث التهديدات الأمنية؟", 1),
            ("Describe a time you had to convince management to invest in security.", "صف موقفاً اضطررت فيه لإقناع الإدارة بالاستثمار في الأمن.", 3),
            ("How do you handle the pressure during a security breach?", "كيف تتعامل مع الضغط أثناء اختراق أمني؟", 3),
            ("Tell me about a time you identified a vulnerability before it was exploited.", "أخبرني عن موقف اكتشفت فيه ثغرة قبل استغلالها.", 3),
            ("How do you balance security with usability?", "كيف توازن بين الأمان وسهولة الاستخدام؟", 3),
            ("Describe a time you had to implement security awareness training.", "صف موقفاً اضطررت فيه لتنفيذ تدريب على الوعي الأمني.", 2),
            ("How do you prioritize security risks in an organization?", "كيف ترتب أولويات المخاطر الأمنية في المؤسسة؟", 3),
            ("Tell me about a time you had to work with a team that was resistant to security policies.", "أخبرني عن موقف اضطررت فيه للعمل مع فريق مقاوم لسياسات الأمان.", 2),
            ("How do you approach security in a cloud-first organization?", "كيف تتعامل مع الأمان في مؤسسة تعتمد السحابة أولاً؟", 2),
            ("Describe a time you had to perform a risk assessment for a new project.", "صف موقفاً اضطررت فيه لإجراء تقييم مخاطر لمشروع جديد.", 2),
            ("How do you handle ethical dilemmas in cybersecurity?", "كيف تتعامل مع المعضلات الأخلاقية في الأمن السيبراني؟", 3),
            ("Tell me about a time you had to communicate a security issue to non-technical executives.", "أخبرني عن موقف اضطررت فيه لإبلاغ مديرين غير تقنيين بمشكلة أمنية.", 2),
            ("How do you mentor junior security professionals?", "كيف توجه المحترفين المبتدئين في مجال الأمن؟", 2),
            ("Describe a security project you led from start to finish.", "صف مشروعاً أمنياً قدته من البداية إلى النهاية.", 3),
        ],
    },

    # ──────────────────────────────────────────
    #  Security Analyst
    # ──────────────────────────────────────────
    "Security Analyst": {
        "technical": [
            ("What is a SIEM system and how do you use it for threat detection?", "ما هو نظام SIEM وكيف تستخدمه لكشف التهديدات؟", 2),
            ("Explain the incident response lifecycle.", "اشرح دورة حياة الاستجابة للحوادث.", 2),
            ("How do you analyze network traffic for suspicious activity?", "كيف تحلل حركة مرور الشبكة للكشف عن نشاط مشبوه؟", 3),
            ("What is threat intelligence and how do you use it?", "ما هو استخبارات التهديدات وكيف تستخدمها؟", 3),
            ("Explain the difference between a false positive and a false negative in security alerts.", "اشرح الفرق بين الإنذار الكاذب والسلبي الكاذب في التنبيهات الأمنية.", 2),
            ("How do you perform log analysis for security monitoring?", "كيف تجري تحليل السجلات للمراقبة الأمنية؟", 3),
            ("What is a SOC and what are its main functions?", "ما هو مركز العمليات الأمنية (SOC) وما وظائفه الرئيسية؟", 2),
            ("Explain the MITRE ATT&CK framework.", "اشرح إطار عمل MITRE ATT&CK.", 3),
            ("How do you create and tune detection rules?", "كيف تنشئ وتضبط قواعد الكشف؟", 3),
            ("What is endpoint detection and response (EDR)?", "ما هو كشف نقطة النهاية والاستجابة (EDR)؟", 2),
            ("How do you investigate a phishing attack?", "كيف تحقق في هجوم تصيد احتيالي؟", 2),
            ("What is malware analysis and what techniques do you use?", "ما هو تحليل البرمجيات الخبيثة وما التقنيات التي تستخدمها؟", 3),
            ("Explain the concept of indicators of compromise (IOCs).", "اشرح مفهوم مؤشرات الاختراق (IOCs).", 2),
            ("How do you handle alert fatigue in security monitoring?", "كيف تتعامل مع إرهاق التنبيهات في المراقبة الأمنية؟", 3),
            ("What is digital forensics and when is it needed?", "ما هو التحقيق الرقمي ومتى يكون مطلوباً؟", 3),
        ],
        "behavioral": [
            ("Tell me about the most challenging security incident you've investigated.", "أخبرني عن أصعب حادث أمني حققت فيه.", 3),
            ("How do you handle the stress of being on-call for security incidents?", "كيف تتعامل مع ضغط المناوبة للحوادث الأمنية؟", 2),
            ("Describe a time you had to escalate a security issue.", "صف موقفاً اضطررت فيه لتصعيد مشكلة أمنية.", 2),
            ("How do you keep your security skills sharp?", "كيف تحافظ على حدة مهاراتك الأمنية؟", 1),
            ("Tell me about a time you reduced false positives in your monitoring.", "أخبرني عن موقف قللت فيه الإنذارات الكاذبة في المراقبة.", 3),
            ("How do you work with other teams during an incident response?", "كيف تعمل مع الفرق الأخرى أثناء الاستجابة لحادث؟", 2),
            ("Describe a situation where you had to make a quick decision during an incident.", "صف موقفاً اضطررت فيه لاتخاذ قرار سريع أثناء حادث.", 3),
            ("How do you document and report on security incidents?", "كيف توثق وتقدم تقارير عن الحوادث الأمنية؟", 2),
            ("Tell me about a time you improved a security monitoring process.", "أخبرني عن موقف حسنت فيه عملية مراقبة أمنية.", 2),
            ("How do you handle situations where you need to investigate a colleague's activity?", "كيف تتعامل مع مواقف تحتاج فيها للتحقيق في نشاط زميل؟", 3),
            ("Describe how you approach continuous learning in cybersecurity.", "صف كيف تتعامل مع التعلم المستمر في الأمن السيبراني.", 1),
            ("Tell me about a time you had to explain a complex threat to management.", "أخبرني عن موقف اضطررت فيه لشرح تهديد معقد للإدارة.", 2),
            ("How do you manage your workload during a major security event?", "كيف تدير عبء عملك أثناء حدث أمني كبير؟", 2),
            ("Describe a time you collaborated with law enforcement on a security matter.", "صف موقفاً تعاونت فيه مع جهات إنفاذ القانون في مسألة أمنية.", 3),
            ("How do you handle burnout in a high-stress security role?", "كيف تتعامل مع الإرهاق في دور أمني عالي الضغط؟", 2),
        ],
    },

    # ──────────────────────────────────────────
    #  Penetration Tester
    # ──────────────────────────────────────────
    "Penetration Tester": {
        "technical": [
            ("Describe the phases of a penetration testing engagement.", "صف مراحل مشروع اختبار الاختراق.", 2),
            ("What is the difference between a vulnerability assessment and a penetration test?", "ما الفرق بين تقييم الثغرات واختبار الاختراق؟", 1),
            ("How do you perform reconnaissance on a target?", "كيف تجري استطلاعاً على هدف ما؟", 2),
            ("What tools do you commonly use for penetration testing?", "ما الأدوات التي تستخدمها عادةً لاختبار الاختراق؟", 2),
            ("Explain how SQL injection works and how to test for it.", "اشرح كيف يعمل حقن SQL وكيف تختبره.", 3),
            ("What is privilege escalation and how do you test for it?", "ما هو تصعيد الصلاحيات وكيف تختبره؟", 3),
            ("How do you test for cross-site scripting (XSS) vulnerabilities?", "كيف تختبر ثغرات البرمجة العابرة للمواقع (XSS)؟", 3),
            ("What is a buffer overflow and how can it be exploited?", "ما هو تجاوز المخزن المؤقت وكيف يمكن استغلاله؟", 4),
            ("Explain the concept of lateral movement in a network.", "اشرح مفهوم الحركة الجانبية في الشبكة.", 3),
            ("How do you write a penetration testing report?", "كيف تكتب تقرير اختبار اختراق؟", 2),
            ("What is wireless network penetration testing?", "ما هو اختبار اختراق الشبكات اللاسلكية؟", 3),
            ("How do you test API security?", "كيف تختبر أمان واجهات API؟", 3),
            ("What is social engineering testing and how do you conduct it?", "ما هو اختبار الهندسة الاجتماعية وكيف تجريه؟", 2),
            ("Explain the concept of red teaming versus penetration testing.", "اشرح الفرق بين الفريق الأحمر واختبار الاختراق.", 3),
            ("How do you handle sensitive data discovered during a penetration test?", "كيف تتعامل مع البيانات الحساسة المكتشفة أثناء اختبار الاختراق؟", 2),
        ],
        "behavioral": [
            ("Tell me about the most interesting vulnerability you've discovered.", "أخبرني عن أكثر ثغرة مثيرة للاهتمام اكتشفتها.", 2),
            ("How do you handle situations where a client disagrees with your findings?", "كيف تتعامل مع مواقف يختلف فيها العميل مع نتائجك؟", 3),
            ("Describe a time you had to stop a test because of potential damage.", "صف موقفاً اضطررت فيه لإيقاف اختبار بسبب احتمال حدوث ضرر.", 3),
            ("How do you maintain ethical standards in penetration testing?", "كيف تحافظ على المعايير الأخلاقية في اختبار الاختراق؟", 2),
            ("Tell me about a time you found a critical vulnerability in a tight timeline.", "أخبرني عن موقف اكتشفت فيه ثغرة حرجة في وقت ضيق.", 3),
            ("How do you prioritize vulnerabilities in your final report?", "كيف ترتب أولويات الثغرات في تقريرك النهائي؟", 2),
            ("Describe a time you had to test a system you were unfamiliar with.", "صف موقفاً اضطررت فيه لاختبار نظام لم تكن مألوفاً به.", 2),
            ("How do you keep your penetration testing skills current?", "كيف تبقي مهارات اختبار الاختراق لديك محدثة؟", 1),
            ("Tell me about a time you had to communicate risk to a non-technical client.", "أخبرني عن موقف اضطررت فيه لإيصال المخاطر لعميل غير تقني.", 2),
            ("How do you handle scope creep during a penetration testing engagement?", "كيف تتعامل مع زحف النطاق أثناء مشروع اختبار اختراق؟", 2),
            ("Describe your approach to continuous improvement in testing methodology.", "صف نهجك في التحسين المستمر لمنهجية الاختبار.", 2),
            ("Tell me about a time you worked with a development team to fix vulnerabilities.", "أخبرني عن موقف عملت فيه مع فريق تطوير لإصلاح ثغرات.", 2),
            ("How do you manage client expectations during an engagement?", "كيف تدير توقعات العميل أثناء المشروع؟", 2),
            ("Describe a time you discovered a zero-day or novel vulnerability.", "صف موقفاً اكتشفت فيه ثغرة يوم صفري أو ثغرة جديدة.", 4),
            ("How do you handle the responsibility of knowing about security weaknesses?", "كيف تتعامل مع مسؤولية معرفتك بنقاط ضعف أمنية؟", 2),
        ],
    },

    # ──────────────────────────────────────────
    #  Security Engineer
    # ──────────────────────────────────────────
    "Security Engineer": {
        "technical": [
            ("How do you design a secure network architecture?", "كيف تصمم بنية شبكة آمنة؟", 3),
            ("Explain the concept of Zero Trust Architecture.", "اشرح مفهوم بنية الثقة المعدومة (Zero Trust).", 3),
            ("What is Identity and Access Management (IAM) and how do you implement it?", "ما هي إدارة الهوية والوصول (IAM) وكيف تنفذها؟", 3),
            ("How do you secure a cloud infrastructure?", "كيف تؤمن بنية تحتية سحابية؟", 3),
            ("What is network segmentation and why is it important?", "ما هو تجزئة الشبكة ولماذا هو مهم؟", 2),
            ("Explain the concept of security automation and orchestration (SOAR).", "اشرح مفهوم أتمتة وتنسيق الأمان (SOAR).", 3),
            ("How do you implement encryption at rest and in transit?", "كيف تنفذ التشفير أثناء التخزين والنقل؟", 3),
            ("What is a Web Application Firewall (WAF) and how does it work?", "ما هو جدار حماية تطبيقات الويب (WAF) وكيف يعمل؟", 2),
            ("How do you secure containerized applications?", "كيف تؤمن التطبيقات المحاوية؟", 3),
            ("Explain the concept of Security as Code.", "اشرح مفهوم الأمان ككود (Security as Code).", 3),
            ("What is DLP and how do you implement it?", "ما هو منع فقدان البيانات (DLP) وكيف تنفذه؟", 3),
            ("How do you conduct a security architecture review?", "كيف تجري مراجعة بنية أمنية؟", 3),
            ("What is certificate management and what best practices do you follow?", "ما هي إدارة الشهادات وما أفضل الممارسات التي تتبعها؟", 2),
            ("Explain how you would secure a CI/CD pipeline.", "اشرح كيف تؤمن خط أنابيب CI/CD.", 3),
            ("What is microsegmentation and how does it enhance security?", "ما هو التجزئة الدقيقة (Microsegmentation) وكيف يعزز الأمان؟", 4),
        ],
        "behavioral": [
            ("Tell me about a security architecture you designed from scratch.", "أخبرني عن بنية أمنية صممتها من الصفر.", 3),
            ("How do you balance security requirements with development velocity?", "كيف توازن بين متطلبات الأمان وسرعة التطوير؟", 3),
            ("Describe a time you had to implement an urgent security fix.", "صف موقفاً اضطررت فيه لتنفيذ إصلاح أمني عاجل.", 3),
            ("How do you work with development teams to embed security early?", "كيف تعمل مع فرق التطوير لتضمين الأمان مبكراً؟", 2),
            ("Tell me about a time you evaluated and selected a security tool.", "أخبرني عن موقف قيمت فيه واخترت أداة أمنية.", 2),
            ("How do you handle pushback from teams on security requirements?", "كيف تتعامل مع مقاومة الفرق لمتطلبات الأمان؟", 2),
            ("Describe a security project that required cross-team collaboration.", "صف مشروعاً أمنياً تطلب تعاوناً بين فرق متعددة.", 3),
            ("How do you approach security in a DevOps environment?", "كيف تتعامل مع الأمان في بيئة DevOps؟", 2),
            ("Tell me about a time you had to respond to a compliance audit finding.", "أخبرني عن موقف اضطررت فيه للاستجابة لنتيجة تدقيق امتثال.", 2),
            ("How do you measure the effectiveness of security controls?", "كيف تقيس فعالية الضوابط الأمنية؟", 3),
            ("Describe a time you had to deprecate an insecure system or practice.", "صف موقفاً اضطررت فيه لإيقاف نظام أو ممارسة غير آمنة.", 2),
            ("How do you communicate security risks to executive leadership?", "كيف تنقل المخاطر الأمنية للقيادة التنفيذية؟", 3),
            ("Tell me about a time you improved an organization's security posture.", "أخبرني عن موقف حسنت فيه الوضع الأمني لمؤسسة.", 3),
            ("How do you handle disagreements with other engineers about security design?", "كيف تتعامل مع الخلافات مع مهندسين آخرين حول التصميم الأمني؟", 2),
            ("Describe your approach to security documentation and runbooks.", "صف نهجك في توثيق الأمان وكتب التشغيل.", 2),
        ],
    },

    # ──────────────────────────────────────────
    #  GRC Specialist
    # ──────────────────────────────────────────
    "GRC Specialist": {
        "technical": [
            ("Explain the ISO 27001 framework and its key components.", "اشرح إطار عمل ISO 27001 ومكوناته الرئيسية.", 2),
            ("What is the NIST Cybersecurity Framework?", "ما هو إطار عمل NIST للأمن السيبراني؟", 2),
            ("How do you conduct a risk assessment?", "كيف تجري تقييم المخاطر؟", 2),
            ("What is the difference between a policy, a standard, and a procedure?", "ما الفرق بين السياسة والمعيار والإجراء؟", 2),
            ("Explain the concept of a risk register.", "اشرح مفهوم سجل المخاطر.", 2),
            ("What is SOC 2 compliance and what are its trust service criteria?", "ما هو امتثال SOC 2 وما معايير خدمة الثقة فيه؟", 3),
            ("How do you manage third-party risk?", "كيف تدير مخاطر الأطراف الثالثة؟", 3),
            ("What is GDPR and what are its key requirements?", "ما هو GDPR وما متطلباته الرئيسية؟", 2),
            ("Explain the concept of business impact analysis (BIA).", "اشرح مفهوم تحليل تأثير الأعمال (BIA).", 3),
            ("What is a business continuity plan and what does it include?", "ما هي خطة استمرارية الأعمال وماذا تتضمن؟", 2),
            ("How do you establish and maintain a compliance program?", "كيف تنشئ وتحافظ على برنامج امتثال؟", 3),
            ("What is the difference between inherent risk and residual risk?", "ما الفرق بين المخاطر الكامنة والمخاطر المتبقية؟", 2),
            ("Explain key performance indicators (KPIs) for a GRC program.", "اشرح مؤشرات الأداء الرئيسية لبرنامج GRC.", 3),
            ("What is an audit trail and why is it important?", "ما هو مسار التدقيق ولماذا هو مهم؟", 2),
            ("How do you handle regulatory changes that affect your organization?", "كيف تتعامل مع التغييرات التنظيمية التي تؤثر على مؤسستك؟", 3),
        ],
        "behavioral": [
            ("Tell me about a time you led an organization through a compliance audit.", "أخبرني عن موقف قدت فيه مؤسسة خلال تدقيق امتثال.", 3),
            ("How do you communicate compliance requirements to technical teams?", "كيف تنقل متطلبات الامتثال للفرق التقنية؟", 2),
            ("Describe a time you identified a significant compliance gap.", "صف موقفاً حددت فيه فجوة امتثال كبيرة.", 3),
            ("How do you handle resistance to compliance policies from employees?", "كيف تتعامل مع مقاومة الموظفين لسياسات الامتثال؟", 2),
            ("Tell me about a time you had to balance business needs with regulatory requirements.", "أخبرني عن موقف اضطررت فيه للموازنة بين احتياجات الأعمال والمتطلبات التنظيمية.", 3),
            ("How do you build a culture of compliance in an organization?", "كيف تبني ثقافة الامتثال في المؤسسة؟", 3),
            ("Describe a time you managed a vendor risk assessment.", "صف موقفاً أدرت فيه تقييم مخاطر مورد.", 2),
            ("How do you stay current with changing regulations and standards?", "كيف تبقى مطلعاً على اللوائح والمعايير المتغيرة؟", 1),
            ("Tell me about a time you developed a risk mitigation strategy.", "أخبرني عن موقف طورت فيه استراتيجية تخفيف المخاطر.", 3),
            ("How do you handle multiple compliance frameworks simultaneously?", "كيف تتعامل مع أطر امتثال متعددة في وقت واحد؟", 3),
            ("Describe how you report on GRC metrics to executive leadership.", "صف كيف تقدم تقارير عن مقاييس GRC للقيادة التنفيذية.", 2),
            ("Tell me about a time you had to handle a data breach notification process.", "أخبرني عن موقف اضطررت فيه للتعامل مع عملية إخطار باختراق بيانات.", 3),
            ("How do you ensure that policies are actually followed, not just written?", "كيف تضمن أن السياسات يتم اتباعها فعلاً وليس مجرد كتابتها؟", 3),
            ("Describe a time you simplified a complex compliance process.", "صف موقفاً بسطت فيه عملية امتثال معقدة.", 2),
            ("How do you handle ethical dilemmas in governance and compliance?", "كيف تتعامل مع المعضلات الأخلاقية في الحوكمة والامتثال؟", 3),
        ],
    },

    # ══════════════════════════════════════════
    #  NETWORKING & CLOUD (Parent)
    # ══════════════════════════════════════════
    "Networking & Cloud": {
        "technical": [
            ("Explain the OSI model and its seven layers.", "اشرح نموذج OSI وطبقاته السبع.", 2),
            ("What is the difference between TCP and UDP?", "ما الفرق بين TCP و UDP؟", 1),
            ("Explain how DNS works.", "اشرح كيف يعمل DNS.", 2),
            ("What is subnetting and why is it used?", "ما هو التقسيم الفرعي للشبكات (Subnetting) ولماذا يُستخدم؟", 2),
            ("Explain the shared responsibility model in cloud computing.", "اشرح نموذج المسؤولية المشتركة في الحوسبة السحابية.", 2),
            ("What is the difference between IaaS, PaaS, and SaaS?", "ما الفرق بين IaaS و PaaS و SaaS؟", 1),
            ("How does load balancing work and what are the common algorithms?", "كيف يعمل توزيع الأحمال وما الخوارزميات الشائعة؟", 2),
            ("What is a CDN and how does it improve performance?", "ما هي شبكة توصيل المحتوى (CDN) وكيف تحسن الأداء؟", 2),
            ("Explain the concept of high availability and fault tolerance.", "اشرح مفهوم التوفر العالي والتسامح مع الأخطاء.", 3),
            ("What is network address translation (NAT) and how does it work?", "ما هو ترجمة عناوين الشبكة (NAT) وكيف يعمل؟", 2),
            ("Explain the difference between public and private cloud.", "اشرح الفرق بين السحابة العامة والخاصة.", 1),
            ("What is software-defined networking (SDN)?", "ما هي الشبكات المعرفة بالبرمجيات (SDN)؟", 3),
            ("How do you troubleshoot network connectivity issues?", "كيف تستكشف مشاكل الاتصال بالشبكة وتصلحها؟", 2),
            ("What is DHCP and how does it assign IP addresses?", "ما هو DHCP وكيف يعين عناوين IP؟", 1),
            ("Explain the concept of disaster recovery in cloud environments.", "اشرح مفهوم التعافي من الكوارث في البيئات السحابية.", 3),
        ],
        "behavioral": [
            ("Tell me about a network issue you troubleshot that was particularly challenging.", "أخبرني عن مشكلة شبكة استكشفتها كانت صعبة بشكل خاص.", 3),
            ("How do you handle network outages and communicate with stakeholders?", "كيف تتعامل مع انقطاعات الشبكة وتتواصل مع أصحاب المصلحة؟", 2),
            ("Describe a time you migrated infrastructure to the cloud.", "صف موقفاً نقلت فيه البنية التحتية إلى السحابة.", 3),
            ("How do you stay current with cloud and networking technologies?", "كيف تبقى مطلعاً على تقنيات السحابة والشبكات؟", 1),
            ("Tell me about a time you optimized network performance.", "أخبرني عن موقف حسنت فيه أداء الشبكة.", 3),
            ("How do you balance cost and performance in cloud infrastructure?", "كيف توازن بين التكلفة والأداء في البنية التحتية السحابية؟", 3),
            ("Describe a time you had to plan network capacity for growth.", "صف موقفاً اضطررت فيه لتخطيط سعة الشبكة للنمو.", 3),
            ("How do you document network architecture and changes?", "كيف توثق بنية الشبكة والتغييرات؟", 2),
            ("Tell me about a time you implemented a disaster recovery plan.", "أخبرني عن موقف نفذت فيه خطة تعافي من الكوارث.", 3),
            ("How do you handle vendor relationships for networking equipment?", "كيف تدير العلاقات مع موردي معدات الشبكات؟", 2),
            ("Describe a time you automated a network or cloud management task.", "صف موقفاً قمت فيه بأتمتة مهمة إدارة شبكة أو سحابة.", 2),
            ("How do you train team members on new technologies?", "كيف تدرب أعضاء الفريق على التقنيات الجديدة؟", 2),
            ("Tell me about a time you reduced cloud costs significantly.", "أخبرني عن موقف قللت فيه تكاليف السحابة بشكل كبير.", 3),
            ("How do you handle security considerations in network design?", "كيف تتعامل مع اعتبارات الأمان في تصميم الشبكة؟", 2),
            ("Describe a time you had to quickly scale infrastructure for an unexpected demand.", "صف موقفاً اضطررت فيه لتوسيع البنية التحتية بسرعة لطلب غير متوقع.", 3),
        ],
    },

    # ──────────────────────────────────────────
    #  Network Engineer
    # ──────────────────────────────────────────
    "Network Engineer": {
        "technical": [
            ("Explain the difference between a router and a switch.", "اشرح الفرق بين الراوتر والسويتش.", 1),
            ("What is VLAN and how do you configure it?", "ما هو VLAN وكيف تقوم بتكوينه؟", 2),
            ("How does OSPF routing protocol work?", "كيف يعمل بروتوكول التوجيه OSPF؟", 3),
            ("What is BGP and when is it used?", "ما هو BGP ومتى يُستخدم؟", 3),
            ("Explain the spanning tree protocol (STP).", "اشرح بروتوكول الشجرة الممتدة (STP).", 3),
            ("How do you configure and manage a VPN?", "كيف تقوم بتكوين وإدارة شبكة VPN؟", 2),
            ("What is QoS and how do you implement it?", "ما هو QoS وكيف تنفذه؟", 3),
            ("Explain the concept of network redundancy.", "اشرح مفهوم التكرار في الشبكة.", 2),
            ("How do you secure a wireless network?", "كيف تؤمن شبكة لاسلكية؟", 2),
            ("What are ACLs and how do you use them?", "ما هي قوائم التحكم بالوصول (ACLs) وكيف تستخدمها؟", 2),
            ("Explain MPLS and its use cases.", "اشرح MPLS وحالات استخدامه.", 3),
            ("How do you monitor network performance and health?", "كيف تراقب أداء وصحة الشبكة؟", 2),
            ("What is SD-WAN and how does it differ from traditional WAN?", "ما هو SD-WAN وكيف يختلف عن WAN التقليدي؟", 3),
            ("How do you troubleshoot intermittent network issues?", "كيف تستكشف مشاكل الشبكة المتقطعة وتصلحها؟", 3),
            ("What is IPv6 and what are the key differences from IPv4?", "ما هو IPv6 وما الاختلافات الرئيسية عن IPv4؟", 2),
        ],
        "behavioral": [
            ("Tell me about a complex network issue you resolved.", "أخبرني عن مشكلة شبكة معقدة قمت بحلها.", 3),
            ("How do you handle network emergencies during off-hours?", "كيف تتعامل مع طوارئ الشبكة خارج ساعات العمل؟", 2),
            ("Describe a time you planned and executed a network upgrade.", "صف موقفاً خططت فيه ونفذت ترقية شبكة.", 3),
            ("How do you keep documentation current for a large network?", "كيف تبقي التوثيق محدثاً لشبكة كبيرة؟", 2),
            ("Tell me about a time you reduced network downtime.", "أخبرني عن موقف قللت فيه وقت توقف الشبكة.", 3),
            ("How do you approach capacity planning for a growing organization?", "كيف تتعامل مع تخطيط السعة لمؤسسة متنامية؟", 3),
            ("Describe a time you had to work with a vendor to resolve a hardware issue.", "صف موقفاً اضطررت فيه للعمل مع مورد لحل مشكلة في العتاد.", 2),
            ("How do you ensure network changes don't disrupt business operations?", "كيف تضمن أن تغييرات الشبكة لا تعطل العمليات التجارية؟", 2),
            ("Tell me about a time you mentored a junior network engineer.", "أخبرني عن موقف وجهت فيه مهندس شبكات مبتدئ.", 2),
            ("How do you handle multiple network projects simultaneously?", "كيف تتعامل مع مشاريع شبكات متعددة في وقت واحد؟", 2),
            ("Describe a time you implemented a network security improvement.", "صف موقفاً نفذت فيه تحسيناً في أمان الشبكة.", 2),
            ("How do you communicate network issues to non-technical staff?", "كيف تشرح مشاكل الشبكة للموظفين غير التقنيين؟", 2),
            ("Tell me about a time you designed a network for a new office or facility.", "أخبرني عن موقف صممت فيه شبكة لمكتب أو منشأة جديدة.", 3),
            ("How do you handle the transition from legacy to modern network equipment?", "كيف تتعامل مع الانتقال من معدات الشبكة القديمة إلى الحديثة؟", 3),
            ("Describe how you approach learning new networking certifications.", "صف كيف تتعامل مع تعلم شهادات شبكات جديدة.", 1),
        ],
    },

    # ──────────────────────────────────────────
    #  Cloud Engineer
    # ──────────────────────────────────────────
    "Cloud Engineer": {
        "technical": [
            ("Compare AWS, Azure, and Google Cloud services.", "قارن بين خدمات AWS و Azure و Google Cloud.", 2),
            ("What is serverless computing and when would you use it?", "ما هي الحوسبة بدون خادم (Serverless) ومتى تستخدمها؟", 2),
            ("How do you design for high availability in the cloud?", "كيف تصمم للتوفر العالي في السحابة؟", 3),
            ("What are the different cloud storage types and their use cases?", "ما هي أنواع التخزين السحابي المختلفة وحالات استخدامها؟", 2),
            ("Explain how auto-scaling works in cloud environments.", "اشرح كيف يعمل التوسع التلقائي في البيئات السحابية.", 2),
            ("What is a VPC and how do you configure it?", "ما هي الشبكة الافتراضية الخاصة (VPC) وكيف تقوم بتكوينها؟", 2),
            ("How do you implement Infrastructure as Code using Terraform?", "كيف تنفذ البنية التحتية ككود باستخدام Terraform؟", 3),
            ("What is cloud cost optimization and what strategies do you use?", "ما هو تحسين تكاليف السحابة وما الاستراتيجيات التي تستخدمها؟", 3),
            ("Explain the concept of multi-cloud and hybrid cloud architectures.", "اشرح مفهوم البنى السحابية المتعددة والهجينة.", 3),
            ("How do you implement cloud security best practices?", "كيف تنفذ أفضل ممارسات أمان السحابة؟", 3),
            ("What is a cloud-native application?", "ما هو التطبيق السحابي الأصلي (Cloud-native)؟", 2),
            ("How do you handle data migration to the cloud?", "كيف تتعامل مع ترحيل البيانات إلى السحابة؟", 3),
            ("What is cloud monitoring and what tools do you use?", "ما هي مراقبة السحابة وما الأدوات التي تستخدمها؟", 2),
            ("Explain the concept of cloud regions and availability zones.", "اشرح مفهوم مناطق السحابة ومناطق التوفر.", 2),
            ("How do you manage IAM roles and policies in AWS?", "كيف تدير أدوار وسياسات IAM في AWS؟", 3),
        ],
        "behavioral": [
            ("Tell me about a cloud migration project you led.", "أخبرني عن مشروع ترحيل سحابي قدته.", 3),
            ("How do you handle unexpected cloud cost spikes?", "كيف تتعامل مع ارتفاعات غير متوقعة في تكاليف السحابة؟", 2),
            ("Describe a time you designed a highly available cloud architecture.", "صف موقفاً صممت فيه بنية سحابية عالية التوفر.", 3),
            ("How do you evaluate and choose between cloud services?", "كيف تقيم وتختار بين الخدمات السحابية؟", 2),
            ("Tell me about a time you resolved a cloud outage.", "أخبرني عن موقف حللت فيه عطلاً سحابياً.", 3),
            ("How do you manage cloud governance across multiple teams?", "كيف تدير حوكمة السحابة عبر فرق متعددة؟", 3),
            ("Describe a time you optimized cloud infrastructure for cost savings.", "صف موقفاً حسنت فيه البنية التحتية السحابية لتوفير التكاليف.", 3),
            ("How do you handle multi-region deployment challenges?", "كيف تتعامل مع تحديات النشر في مناطق متعددة؟", 3),
            ("Tell me about a time you automated cloud infrastructure provisioning.", "أخبرني عن موقف قمت فيه بأتمتة توفير البنية التحتية السحابية.", 2),
            ("How do you ensure compliance in cloud environments?", "كيف تضمن الامتثال في البيئات السحابية؟", 2),
            ("Describe a time you had to quickly scale cloud resources.", "صف موقفاً اضطررت فيه لتوسيع الموارد السحابية بسرعة.", 2),
            ("How do you train your team on cloud best practices?", "كيف تدرب فريقك على أفضل ممارسات السحابة؟", 2),
            ("Tell me about a cloud security incident you handled.", "أخبرني عن حادث أمني سحابي تعاملت معه.", 3),
            ("How do you approach vendor lock-in concerns?", "كيف تتعامل مع مخاوف الارتباط بمزود واحد؟", 3),
            ("Describe how you keep up with the rapid pace of cloud service updates.", "صف كيف تواكب الوتيرة السريعة لتحديثات الخدمات السحابية.", 1),
        ],
    },

    # ──────────────────────────────────────────
    #  Systems Administrator
    # ──────────────────────────────────────────
    "Systems Administrator": {
        "technical": [
            ("What are the key differences between Linux and Windows server administration?", "ما الاختلافات الرئيسية بين إدارة خوادم Linux و Windows؟", 2),
            ("How do you manage user accounts and permissions on Linux?", "كيف تدير حسابات المستخدمين والصلاحيات على Linux؟", 2),
            ("What is RAID and what are the different RAID levels?", "ما هو RAID وما مستوياته المختلفة؟", 2),
            ("How do you automate system administration tasks?", "كيف تؤتمت مهام إدارة الأنظمة؟", 2),
            ("Explain the concept of system hardening.", "اشرح مفهوم تعزيز النظام (System Hardening).", 2),
            ("How do you manage and rotate system backups?", "كيف تدير وتدور النسخ الاحتياطية للنظام؟", 2),
            ("What is Active Directory and how does it work?", "ما هو Active Directory وكيف يعمل؟", 2),
            ("How do you monitor system performance and resource usage?", "كيف تراقب أداء النظام واستخدام الموارد؟", 2),
            ("What is configuration management and what tools do you use?", "ما هي إدارة التكوين وما الأدوات التي تستخدمها؟", 2),
            ("How do you handle patch management across multiple systems?", "كيف تدير التصحيحات عبر أنظمة متعددة؟", 2),
            ("What is NFS and how do you set up file sharing?", "ما هو NFS وكيف تعد مشاركة الملفات؟", 2),
            ("How do you troubleshoot a server that won't boot?", "كيف تستكشف خطأ في خادم لا يقلع وتصلحه؟", 3),
            ("Explain the concept of virtualization and its benefits.", "اشرح مفهوم الافتراضية (Virtualization) وفوائدها.", 2),
            ("How do you implement a centralized logging system?", "كيف تنفذ نظام تسجيل مركزي؟", 3),
            ("What is LDAP and how is it used for authentication?", "ما هو LDAP وكيف يُستخدم للمصادقة؟", 2),
        ],
        "behavioral": [
            ("Tell me about a critical server failure you resolved.", "أخبرني عن عطل خادم حرج قمت بحله.", 3),
            ("How do you handle multiple urgent requests simultaneously?", "كيف تتعامل مع طلبات عاجلة متعددة في وقت واحد؟", 2),
            ("Describe a time you improved system reliability.", "صف موقفاً حسنت فيه موثوقية النظام.", 3),
            ("How do you manage system changes in a production environment?", "كيف تدير تغييرات النظام في بيئة الإنتاج؟", 2),
            ("Tell me about a time you automated a repetitive task.", "أخبرني عن موقف قمت فيه بأتمتة مهمة متكررة.", 2),
            ("How do you handle after-hours support and on-call duties?", "كيف تتعامل مع الدعم خارج ساعات العمل ومهام المناوبة؟", 2),
            ("Describe a time you had to recover data from a failed system.", "صف موقفاً اضطررت فيه لاستعادة بيانات من نظام فاشل.", 3),
            ("How do you ensure system documentation is kept up to date?", "كيف تضمن بقاء توثيق النظام محدثاً؟", 2),
            ("Tell me about a time you migrated servers with minimal downtime.", "أخبرني عن موقف نقلت فيه خوادم مع أقل وقت توقف ممكن.", 3),
            ("How do you approach security patching in a large environment?", "كيف تتعامل مع التصحيحات الأمنية في بيئة كبيرة؟", 2),
            ("Describe a time you provided technical support to non-technical users.", "صف موقفاً قدمت فيه دعماً تقنياً لمستخدمين غير تقنيين.", 1),
            ("How do you handle end-of-life hardware and software transitions?", "كيف تتعامل مع انتقالات العتاد والبرمجيات المنتهية الدعم؟", 2),
            ("Tell me about a time you improved system performance significantly.", "أخبرني عن موقف حسنت فيه أداء النظام بشكل كبير.", 3),
            ("How do you manage the lifecycle of IT assets?", "كيف تدير دورة حياة أصول تكنولوجيا المعلومات؟", 2),
            ("Describe how you handle vendor support escalations.", "صف كيف تتعامل مع تصعيدات دعم الموردين.", 2),
        ],
    },

    # ══════════════════════════════════════════
    #  INFORMATION SYSTEMS & BUSINESS (Parent)
    # ══════════════════════════════════════════
    "Information Systems & Business": {
        "technical": [
            ("What is a business requirements document (BRD) and what does it contain?", "ما هي وثيقة متطلبات الأعمال (BRD) وماذا تحتوي؟", 2),
            ("Explain the difference between functional and non-functional requirements.", "اشرح الفرق بين المتطلبات الوظيفية وغير الوظيفية.", 2),
            ("What is a use case diagram and how do you create one?", "ما هو مخطط حالة الاستخدام وكيف تنشئ واحداً؟", 2),
            ("Explain the agile methodology and its key ceremonies.", "اشرح منهجية أجايل واحتفالاتها الرئيسية.", 2),
            ("What is a process flow diagram and when do you use it?", "ما هو مخطط تدفق العمليات ومتى تستخدمه؟", 2),
            ("How do you perform a gap analysis?", "كيف تجري تحليل الفجوات؟", 2),
            ("What is a data flow diagram (DFD)?", "ما هو مخطط تدفق البيانات (DFD)؟", 2),
            ("Explain the concept of total cost of ownership (TCO) for IT systems.", "اشرح مفهوم التكلفة الإجمالية للملكية (TCO) لأنظمة تكنولوجيا المعلومات.", 3),
            ("What is change management in IT projects?", "ما هي إدارة التغيير في مشاريع تكنولوجيا المعلومات؟", 2),
            ("How do you measure ROI for technology investments?", "كيف تقيس العائد على الاستثمار لاستثمارات التكنولوجيا؟", 3),
            ("What is ITIL and what are its key processes?", "ما هو ITIL وما عملياته الرئيسية؟", 2),
            ("Explain the concept of digital transformation.", "اشرح مفهوم التحول الرقمي.", 2),
            ("What is an SLA and what does it typically include?", "ما هي اتفاقية مستوى الخدمة (SLA) وماذا تتضمن عادةً؟", 2),
            ("How do you conduct a feasibility study for a new system?", "كيف تجري دراسة جدوى لنظام جديد؟", 3),
            ("What is enterprise architecture and why is it important?", "ما هي بنية المؤسسة ولماذا هي مهمة؟", 3),
        ],
        "behavioral": [
            ("Tell me about a time you bridged the gap between business and technology teams.", "أخبرني عن موقف سددت فيه الفجوة بين فرق الأعمال والتكنولوجيا.", 3),
            ("How do you handle conflicting requirements from different stakeholders?", "كيف تتعامل مع متطلبات متعارضة من أصحاب مصلحة مختلفين؟", 3),
            ("Describe a time you managed a project that went over budget or schedule.", "صف موقفاً أدرت فيه مشروعاً تجاوز الميزانية أو الجدول الزمني.", 3),
            ("How do you ensure user adoption of a new system?", "كيف تضمن تبني المستخدمين لنظام جديد؟", 2),
            ("Tell me about a time you had to make a difficult trade-off in a project.", "أخبرني عن موقف اضطررت فيه لاتخاذ مفاضلة صعبة في مشروع.", 3),
            ("How do you manage stakeholder expectations?", "كيف تدير توقعات أصحاب المصلحة؟", 2),
            ("Describe a time you successfully delivered a project under tight constraints.", "صف موقفاً نجحت فيه بتسليم مشروع تحت قيود ضيقة.", 3),
            ("How do you handle resistance to new technology implementations?", "كيف تتعامل مع مقاومة تطبيقات التكنولوجيا الجديدة؟", 2),
            ("Tell me about a time you facilitated a requirements workshop.", "أخبرني عن موقف أدرت فيه ورشة عمل لجمع المتطلبات.", 2),
            ("How do you prioritize features in a product backlog?", "كيف ترتب أولويات الميزات في قائمة المنتج المتراكمة؟", 2),
            ("Describe a time you improved a business process through technology.", "صف موقفاً حسنت فيه عملية أعمال من خلال التكنولوجيا.", 3),
            ("How do you handle scope creep in projects?", "كيف تتعامل مع زحف النطاق في المشاريع؟", 2),
            ("Tell me about a time you led a cross-functional team.", "أخبرني عن موقف قدت فيه فريقاً متعدد التخصصات.", 3),
            ("How do you ensure quality throughout the project lifecycle?", "كيف تضمن الجودة طوال دورة حياة المشروع؟", 2),
            ("Describe how you approach continuous improvement in your work.", "صف كيف تتعامل مع التحسين المستمر في عملك.", 2),
        ],
    },

    # ──────────────────────────────────────────
    #  Business Analyst
    # ──────────────────────────────────────────
    "Business Analyst": {
        "technical": [
            ("How do you gather and document business requirements?", "كيف تجمع وتوثق متطلبات الأعمال؟", 2),
            ("What is a user story and how do you write one?", "ما هي قصة المستخدم وكيف تكتب واحدة؟", 1),
            ("Explain how you create a SWOT analysis.", "اشرح كيف تنشئ تحليل SWOT.", 2),
            ("What is stakeholder mapping and how do you perform it?", "ما هو تخطيط أصحاب المصلحة وكيف تجريه؟", 2),
            ("How do you create acceptance criteria for a user story?", "كيف تنشئ معايير القبول لقصة مستخدم؟", 2),
            ("What is a wireframe and when do you use it in requirements gathering?", "ما هو الـ Wireframe ومتى تستخدمه في جمع المتطلبات؟", 2),
            ("How do you perform cost-benefit analysis?", "كيف تجري تحليل التكلفة والفائدة؟", 3),
            ("What is MoSCoW prioritization?", "ما هو ترتيب أولويات MoSCoW؟", 2),
            ("How do you create a business process model?", "كيف تنشئ نموذج عمليات الأعمال؟", 2),
            ("What is a traceability matrix and why is it important?", "ما هي مصفوفة التتبع ولماذا هي مهمة؟", 2),
            ("How do you validate requirements with stakeholders?", "كيف تتحقق من المتطلبات مع أصحاب المصلحة؟", 2),
            ("What is the difference between Agile and Waterfall from a BA perspective?", "ما الفرق بين أجايل والشلال من منظور محلل الأعمال؟", 2),
            ("How do you handle conflicting requirements?", "كيف تتعامل مع المتطلبات المتعارضة؟", 3),
            ("What tools do you use for requirements management?", "ما الأدوات التي تستخدمها لإدارة المتطلبات؟", 1),
            ("How do you measure the success of a project or feature?", "كيف تقيس نجاح مشروع أو ميزة؟", 3),
        ],
        "behavioral": [
            ("Tell me about a time you uncovered a hidden requirement that changed the project direction.", "أخبرني عن موقف اكتشفت فيه متطلباً مخفياً غيّر اتجاه المشروع.", 3),
            ("How do you build trust with stakeholders?", "كيف تبني الثقة مع أصحاب المصلحة؟", 2),
            ("Describe a time you had to push back on a stakeholder request.", "صف موقفاً اضطررت فيه لرفض طلب من صاحب مصلحة.", 3),
            ("How do you handle situations where business needs conflict with technical constraints?", "كيف تتعامل مع مواقف تتعارض فيها احتياجات الأعمال مع القيود التقنية؟", 3),
            ("Tell me about a requirements gap you identified that prevented a major issue.", "أخبرني عن فجوة متطلبات حددتها ومنعت مشكلة كبيرة.", 3),
            ("How do you facilitate meetings with diverse stakeholders?", "كيف تدير اجتماعات مع أصحاب مصلحة متنوعين؟", 2),
            ("Describe a time you translated complex technical concepts for business users.", "صف موقفاً ترجمت فيه مفاهيم تقنية معقدة لمستخدمي الأعمال.", 2),
            ("How do you handle ambiguity in the early stages of a project?", "كيف تتعامل مع الغموض في المراحل المبكرة من المشروع؟", 2),
            ("Tell me about a time you improved a business process.", "أخبرني عن موقف حسنت فيه عملية أعمال.", 2),
            ("How do you manage scope changes during a project?", "كيف تدير تغييرات النطاق أثناء المشروع؟", 2),
            ("Describe a time you had to work with a difficult stakeholder.", "صف موقفاً اضطررت فيه للعمل مع صاحب مصلحة صعب.", 3),
            ("How do you ensure requirements are complete and testable?", "كيف تضمن أن المتطلبات كاملة وقابلة للاختبار؟", 2),
            ("Tell me about a time your analysis had a significant impact on the business.", "أخبرني عن موقف كان لتحليلك فيه تأثير كبير على الأعمال.", 3),
            ("How do you handle last-minute changes to requirements?", "كيف تتعامل مع تغييرات اللحظة الأخيرة على المتطلبات؟", 2),
            ("Describe how you collaborate with development teams.", "صف كيف تتعاون مع فرق التطوير.", 2),
        ],
    },

    # ──────────────────────────────────────────
    #  ERP Consultant
    # ──────────────────────────────────────────
    "ERP Consultant": {
        "technical": [
            ("What are the main modules of an ERP system?", "ما هي الوحدات الرئيسية لنظام ERP؟", 1),
            ("How do you approach ERP implementation methodology?", "كيف تتعامل مع منهجية تنفيذ ERP؟", 2),
            ("What is the difference between ERP customization and configuration?", "ما الفرق بين تخصيص وتكوين ERP؟", 2),
            ("How do you handle data migration in an ERP project?", "كيف تتعامل مع ترحيل البيانات في مشروع ERP؟", 3),
            ("What is master data management in ERP?", "ما هي إدارة البيانات الرئيسية في ERP؟", 2),
            ("How do you perform ERP system integration testing?", "كيف تجري اختبار تكامل نظام ERP؟", 3),
            ("What are SAP FICO modules and their key functions?", "ما هي وحدات SAP FICO ووظائفها الرئيسية؟", 2),
            ("How do you handle change requests during ERP implementation?", "كيف تتعامل مع طلبات التغيير أثناء تنفيذ ERP؟", 2),
            ("What is the difference between on-premise and cloud ERP?", "ما الفرق بين ERP المحلي والسحابي؟", 2),
            ("How do you design business processes in an ERP system?", "كيف تصمم العمليات التجارية في نظام ERP؟", 3),
            ("What are the key considerations for ERP go-live?", "ما الاعتبارات الرئيسية لإطلاق ERP؟", 3),
            ("How do you handle ERP user training?", "كيف تتعامل مع تدريب مستخدمي ERP؟", 2),
            ("What is ERP security and role-based access control?", "ما هو أمان ERP والتحكم بالوصول المبني على الأدوار؟", 2),
            ("How do you create functional specifications for ERP development?", "كيف تنشئ المواصفات الوظيفية لتطوير ERP؟", 3),
            ("What are common ERP implementation risks and how do you mitigate them?", "ما هي مخاطر تنفيذ ERP الشائعة وكيف تخففها؟", 3),
        ],
        "behavioral": [
            ("Tell me about an ERP implementation project you led or contributed to.", "أخبرني عن مشروع تنفيذ ERP قدته أو ساهمت فيه.", 3),
            ("How do you handle resistance from users during ERP go-live?", "كيف تتعامل مع مقاومة المستخدمين أثناء إطلاق ERP؟", 2),
            ("Describe a time you had to resolve a complex ERP integration issue.", "صف موقفاً اضطررت فيه لحل مشكلة تكامل ERP معقدة.", 3),
            ("How do you manage stakeholder expectations during long ERP projects?", "كيف تدير توقعات أصحاب المصلحة خلال مشاريع ERP الطويلة؟", 3),
            ("Tell me about a time you customized an ERP module to fit a unique business process.", "أخبرني عن موقف خصصت فيه وحدة ERP لتناسب عملية أعمال فريدة.", 3),
            ("How do you approach knowledge transfer at the end of an ERP project?", "كيف تتعامل مع نقل المعرفة في نهاية مشروع ERP؟", 2),
            ("Describe a data migration challenge you faced and how you resolved it.", "صف تحدي ترحيل بيانات واجهته وكيف حللته.", 3),
            ("How do you balance best practices with client-specific requirements?", "كيف توازن بين أفضل الممارسات ومتطلبات العميل الخاصة؟", 3),
            ("Tell me about a time an ERP project faced significant delays.", "أخبرني عن موقف واجه فيه مشروع ERP تأخيرات كبيرة.", 3),
            ("How do you handle training users with varying technical skill levels?", "كيف تتعامل مع تدريب مستخدمين بمستويات مهارات تقنية متفاوتة؟", 2),
            ("Describe a time you identified a process improvement during an ERP implementation.", "صف موقفاً حددت فيه تحسيناً في العمليات أثناء تنفيذ ERP.", 2),
            ("How do you document ERP configurations and customizations?", "كيف توثق تكوينات وتخصيصات ERP؟", 2),
            ("Tell me about a time you had to work with multiple departments on an ERP rollout.", "أخبرني عن موقف اضطررت فيه للعمل مع أقسام متعددة في طرح ERP.", 2),
            ("How do you handle post-implementation support?", "كيف تتعامل مع الدعم بعد التنفيذ؟", 2),
            ("Describe how you stay current with ERP technology trends.", "صف كيف تبقى مطلعاً على اتجاهات تقنية ERP.", 1),
        ],
    },

    # ──────────────────────────────────────────
    #  IT Project Manager
    # ──────────────────────────────────────────
    "IT Project Manager": {
        "technical": [
            ("What is the difference between Agile and Waterfall project management?", "ما الفرق بين إدارة المشاريع بأسلوب أجايل والشلال؟", 1),
            ("How do you create a project charter?", "كيف تنشئ ميثاق المشروع؟", 2),
            ("What is a work breakdown structure (WBS)?", "ما هي هيكلة تقسيم العمل (WBS)؟", 2),
            ("How do you estimate project timelines and resources?", "كيف تقدّر الجداول الزمنية والموارد للمشروع؟", 2),
            ("What is a Gantt chart and how do you use it?", "ما هو مخطط غانت وكيف تستخدمه؟", 1),
            ("How do you identify and manage project risks?", "كيف تحدد وتدير مخاطر المشروع؟", 2),
            ("What is earned value management (EVM)?", "ما هي إدارة القيمة المكتسبة (EVM)؟", 3),
            ("How do you manage project scope and prevent scope creep?", "كيف تدير نطاق المشروع وتمنع زحف النطاق؟", 2),
            ("What are the key Scrum ceremonies and their purposes?", "ما هي احتفالات Scrum الرئيسية وأغراضها؟", 2),
            ("How do you track and report project progress?", "كيف تتتبع وتقدم تقارير عن تقدم المشروع؟", 2),
            ("What is the critical path method?", "ما هي طريقة المسار الحرج؟", 3),
            ("How do you manage project budgets?", "كيف تدير ميزانيات المشروع؟", 2),
            ("What is a RACI matrix and how do you use it?", "ما هي مصفوفة RACI وكيف تستخدمها؟", 2),
            ("How do you handle project change requests?", "كيف تتعامل مع طلبات تغيير المشروع؟", 2),
            ("What are the key project management tools you use?", "ما هي أدوات إدارة المشاريع الرئيسية التي تستخدمها؟", 1),
        ],
        "behavioral": [
            ("Tell me about a project that was at risk of failure and how you turned it around.", "أخبرني عن مشروع كان معرضاً للفشل وكيف أنقذته.", 3),
            ("How do you handle conflicts between team members?", "كيف تتعامل مع النزاعات بين أعضاء الفريق؟", 2),
            ("Describe a time you had to deliver bad news to a stakeholder.", "صف موقفاً اضطررت فيه لتقديم أخبار سيئة لصاحب مصلحة.", 3),
            ("How do you motivate a team during a challenging project?", "كيف تحفز الفريق خلال مشروع صعب؟", 2),
            ("Tell me about a time you managed multiple projects simultaneously.", "أخبرني عن موقف أدرت فيه مشاريع متعددة في وقت واحد.", 2),
            ("How do you handle a team member who is consistently underperforming?", "كيف تتعامل مع عضو فريق يقدم أداءً ضعيفاً باستمرار؟", 3),
            ("Describe a time you successfully negotiated project resources.", "صف موقفاً نجحت فيه بالتفاوض على موارد المشروع.", 3),
            ("How do you ensure effective communication across project teams?", "كيف تضمن التواصل الفعال عبر فرق المشروع؟", 2),
            ("Tell me about a time you had to adapt your project management approach.", "أخبرني عن موقف اضطررت فيه لتكييف نهجك في إدارة المشاريع.", 2),
            ("How do you handle unrealistic deadlines from management?", "كيف تتعامل مع مواعيد نهائية غير واقعية من الإدارة؟", 3),
            ("Describe a time you managed a project with remote team members.", "صف موقفاً أدرت فيه مشروعاً مع أعضاء فريق عن بُعد.", 2),
            ("How do you conduct effective post-project reviews?", "كيف تجري مراجعات فعالة بعد المشروع؟", 2),
            ("Tell me about a time you had to manage vendor relationships.", "أخبرني عن موقف اضطررت فيه لإدارة العلاقات مع الموردين.", 2),
            ("How do you balance quality, time, and cost in project management?", "كيف توازن بين الجودة والوقت والتكلفة في إدارة المشاريع؟", 3),
            ("Describe your approach to building and developing a project team.", "صف نهجك في بناء وتطوير فريق المشروع.", 2),
        ],
    },

    # ──────────────────────────────────────────
    #  Product Manager
    # ──────────────────────────────────────────
    "Product Manager": {
        "technical": [
            ("How do you define and measure product-market fit?", "كيف تحدد وتقيس ملاءمة المنتج للسوق؟", 3),
            ("What is a product roadmap and how do you create one?", "ما هي خارطة طريق المنتج وكيف تنشئ واحدة؟", 2),
            ("How do you prioritize features using frameworks like RICE or ICE?", "كيف ترتب أولويات الميزات باستخدام أطر مثل RICE أو ICE؟", 2),
            ("What are OKRs and how do you use them for product goals?", "ما هي OKRs وكيف تستخدمها لأهداف المنتج؟", 2),
            ("How do you conduct competitive analysis?", "كيف تجري تحليل المنافسة؟", 2),
            ("What is a minimum viable product (MVP) and how do you define it?", "ما هو الحد الأدنى من المنتج القابل للتطبيق (MVP) وكيف تحدده؟", 2),
            ("How do you use data to inform product decisions?", "كيف تستخدم البيانات لاتخاذ قرارات المنتج؟", 3),
            ("What is a product backlog and how do you manage it?", "ما هي قائمة المنتج المتراكمة وكيف تديرها؟", 2),
            ("How do you define and track product metrics?", "كيف تحدد وتتتبع مقاييس المنتج؟", 2),
            ("What is a go-to-market strategy?", "ما هي استراتيجية الذهاب إلى السوق؟", 3),
            ("How do you create and validate product hypotheses?", "كيف تنشئ وتتحقق من فرضيات المنتج؟", 3),
            ("What is product lifecycle management?", "ما هي إدارة دورة حياة المنتج؟", 2),
            ("How do you use customer journey mapping?", "كيف تستخدم تخطيط رحلة العميل؟", 2),
            ("What is a value proposition and how do you craft one?", "ما هي القيمة المقترحة وكيف تصوغ واحدة؟", 2),
            ("How do you balance technical debt with new feature development?", "كيف توازن بين الدين التقني وتطوير ميزات جديدة؟", 3),
        ],
        "behavioral": [
            ("Tell me about a product decision you made based on data.", "أخبرني عن قرار منتج اتخذته بناءً على البيانات.", 3),
            ("How do you handle disagreements with engineering on product priorities?", "كيف تتعامل مع الخلافات مع الهندسة حول أولويات المنتج؟", 3),
            ("Describe a time you had to kill a feature or product.", "صف موقفاً اضطررت فيه لإلغاء ميزة أو منتج.", 3),
            ("How do you gather and act on customer feedback?", "كيف تجمع ملاحظات العملاء وتتصرف بناءً عليها؟", 2),
            ("Tell me about a time you successfully launched a new product or feature.", "أخبرني عن موقف أطلقت فيه منتجاً أو ميزة جديدة بنجاح.", 3),
            ("How do you align multiple stakeholders around a product vision?", "كيف توحد أصحاب المصلحة المتعددين حول رؤية المنتج؟", 3),
            ("Describe a time you had to say no to a stakeholder request.", "صف موقفاً اضطررت فيه لرفض طلب من صاحب مصلحة.", 3),
            ("How do you handle a product that isn't meeting its targets?", "كيف تتعامل مع منتج لا يحقق أهدافه؟", 3),
            ("Tell me about a time you pivoted your product strategy.", "أخبرني عن موقف غيرت فيه استراتيجية منتجك.", 3),
            ("How do you balance user needs with business objectives?", "كيف توازن بين احتياجات المستخدم وأهداف الأعمال؟", 3),
            ("Describe a time you worked with design to improve user experience.", "صف موقفاً عملت فيه مع التصميم لتحسين تجربة المستخدم.", 2),
            ("How do you manage your product backlog effectively?", "كيف تدير قائمة منتجك المتراكمة بفعالية؟", 2),
            ("Tell me about a time you influenced without authority.", "أخبرني عن موقف أثرت فيه بدون سلطة رسمية.", 3),
            ("How do you communicate product strategy to different audiences?", "كيف تنقل استراتيجية المنتج لجماهير مختلفة؟", 2),
            ("Describe how you approach product discovery.", "صف كيف تتعامل مع اكتشاف المنتج.", 2),
        ],
    },

    # ──────────────────────────────────────────
    #  IT Auditor
    # ──────────────────────────────────────────
    "IT Auditor": {
        "technical": [
            ("What is the difference between internal and external IT audits?", "ما الفرق بين التدقيق الداخلي والخارجي لتكنولوجيا المعلومات؟", 1),
            ("How do you plan and scope an IT audit?", "كيف تخطط وتحدد نطاق تدقيق تكنولوجيا المعلومات؟", 2),
            ("What are IT general controls (ITGC)?", "ما هي ضوابط تكنولوجيا المعلومات العامة (ITGC)؟", 2),
            ("How do you assess the effectiveness of IT controls?", "كيف تقيم فعالية ضوابط تكنولوجيا المعلومات؟", 3),
            ("What is COBIT and how is it used in IT auditing?", "ما هو COBIT وكيف يُستخدم في تدقيق تكنولوجيا المعلومات؟", 2),
            ("How do you audit access controls and user provisioning?", "كيف تدقق ضوابط الوصول وتوفير المستخدمين؟", 2),
            ("What is a control deficiency versus a material weakness?", "ما الفرق بين قصور الرقابة والضعف الجوهري؟", 3),
            ("How do you audit change management processes?", "كيف تدقق عمليات إدارة التغيير؟", 2),
            ("What is continuous auditing and monitoring?", "ما هو التدقيق والمراقبة المستمرة؟", 3),
            ("How do you use data analytics in IT auditing?", "كيف تستخدم تحليلات البيانات في تدقيق تكنولوجيا المعلومات؟", 3),
            ("What is the audit evidence lifecycle?", "ما هي دورة حياة أدلة التدقيق؟", 2),
            ("How do you audit disaster recovery and business continuity plans?", "كيف تدقق خطط التعافي من الكوارث واستمرارية الأعمال؟", 3),
            ("What is the role of IT audit in SOX compliance?", "ما هو دور تدقيق تكنولوجيا المعلومات في امتثال SOX؟", 3),
            ("How do you assess IT governance maturity?", "كيف تقيم نضج حوكمة تكنولوجيا المعلومات؟", 3),
            ("What are common IT audit findings and recommendations?", "ما هي نتائج وتوصيات تدقيق تكنولوجيا المعلومات الشائعة؟", 2),
        ],
        "behavioral": [
            ("Tell me about an audit finding that led to significant organizational change.", "أخبرني عن نتيجة تدقيق أدت إلى تغيير تنظيمي كبير.", 3),
            ("How do you handle pushback from auditees on your findings?", "كيف تتعامل مع مقاومة الجهات المدققة لنتائجك؟", 3),
            ("Describe a time you had to report a sensitive finding.", "صف موقفاً اضطررت فيه للإبلاغ عن نتيجة حساسة.", 3),
            ("How do you maintain independence and objectivity as an auditor?", "كيف تحافظ على الاستقلالية والموضوعية كمدقق؟", 2),
            ("Tell me about a complex audit project you managed.", "أخبرني عن مشروع تدقيق معقد أدرته.", 3),
            ("How do you communicate audit findings to non-technical management?", "كيف تنقل نتائج التدقيق للإدارة غير التقنية؟", 2),
            ("Describe a time you identified a control weakness others had missed.", "صف موقفاً حددت فيه ضعفاً في الرقابة فاته آخرون.", 3),
            ("How do you follow up on audit recommendations?", "كيف تتابع توصيات التدقيق؟", 2),
            ("Tell me about a time you had to work with a tight audit deadline.", "أخبرني عن موقف اضطررت فيه للعمل بموعد نهائي ضيق للتدقيق.", 2),
            ("How do you build relationships with the teams you audit?", "كيف تبني علاقات مع الفرق التي تدققها؟", 2),
            ("Describe a time you had to adapt your audit approach mid-project.", "صف موقفاً اضطررت فيه لتكييف نهج التدقيق أثناء المشروع.", 2),
            ("How do you ensure audit quality and consistency?", "كيف تضمن جودة واتساق التدقيق؟", 2),
            ("Tell me about a time you mentored a junior auditor.", "أخبرني عن موقف وجهت فيه مدققاً مبتدئاً.", 2),
            ("How do you manage multiple audits at the same time?", "كيف تدير تدقيقات متعددة في نفس الوقت؟", 2),
            ("Describe how you stay updated with auditing standards and regulations.", "صف كيف تبقى مطلعاً على معايير ولوائح التدقيق.", 1),
        ],
    },

    # ══════════════════════════════════════════
    #  UX & DESIGN (Parent)
    # ══════════════════════════════════════════
    "UX & Design": {
        "technical": [
            ("What is the difference between UX and UI design?", "ما الفرق بين تصميم تجربة المستخدم وتصميم واجهة المستخدم؟", 1),
            ("Explain the design thinking process.", "اشرح عملية التفكير التصميمي.", 2),
            ("What is a design system and why is it important?", "ما هو نظام التصميم ولماذا هو مهم؟", 2),
            ("How do you conduct a heuristic evaluation?", "كيف تجري تقييماً إرشادياً (Heuristic Evaluation)؟", 3),
            ("What are the key principles of visual hierarchy?", "ما هي المبادئ الرئيسية للتسلسل الهرمي البصري؟", 2),
            ("Explain the concept of information architecture.", "اشرح مفهوم هندسة المعلومات.", 2),
            ("What is responsive design and adaptive design?", "ما هو التصميم المتجاوب والتصميم التكيفي؟", 2),
            ("How do you create user personas?", "كيف تنشئ شخصيات المستخدم (Personas)؟", 2),
            ("What are accessibility standards and why do they matter?", "ما هي معايير إمكانية الوصول ولماذا هي مهمة؟", 2),
            ("Explain the concept of micro-interactions.", "اشرح مفهوم التفاعلات الدقيقة (Micro-interactions).", 3),
            ("What is a user flow and how do you create one?", "ما هو تدفق المستخدم وكيف تنشئ واحداً؟", 2),
            ("How do you measure the usability of a product?", "كيف تقيس قابلية استخدام المنتج؟", 2),
            ("What is color theory and how does it apply to UI design?", "ما هي نظرية الألوان وكيف تُطبَّق في تصميم الواجهة؟", 2),
            ("Explain the concept of progressive disclosure.", "اشرح مفهوم الكشف التدريجي (Progressive Disclosure).", 3),
            ("What are design tokens and how are they used?", "ما هي رموز التصميم (Design Tokens) وكيف تُستخدم؟", 3),
        ],
        "behavioral": [
            ("Tell me about a design that significantly improved user engagement.", "أخبرني عن تصميم حسّن مشاركة المستخدم بشكل كبير.", 3),
            ("How do you handle design feedback that conflicts with your vision?", "كيف تتعامل مع ملاحظات تصميم تتعارض مع رؤيتك؟", 3),
            ("Describe a time you had to design under strict constraints.", "صف موقفاً اضطررت فيه للتصميم تحت قيود صارمة.", 3),
            ("How do you advocate for user needs when business goals conflict?", "كيف تدافع عن احتياجات المستخدم عندما تتعارض أهداف الأعمال؟", 3),
            ("Tell me about a design failure and what you learned from it.", "أخبرني عن فشل تصميمي وماذا تعلمت منه.", 3),
            ("How do you collaborate with developers to implement your designs?", "كيف تتعاون مع المطورين لتنفيذ تصاميمك؟", 2),
            ("Describe how you stay current with design trends.", "صف كيف تبقى مطلعاً على اتجاهات التصميم.", 1),
            ("Tell me about a time you designed for accessibility.", "أخبرني عن موقف صممت فيه لإمكانية الوصول.", 2),
            ("How do you handle tight deadlines in design projects?", "كيف تتعامل مع المواعيد النهائية الضيقة في مشاريع التصميم؟", 2),
            ("Describe a time you had to redesign an existing product.", "صف موقفاً اضطررت فيه لإعادة تصميم منتج قائم.", 3),
            ("How do you present and defend your design decisions?", "كيف تقدم وتدافع عن قرارات التصميم الخاصة بك؟", 2),
            ("Tell me about a time data changed your design direction.", "أخبرني عن موقف غيرت فيه البيانات اتجاه تصميمك.", 3),
            ("How do you manage design consistency across a large product?", "كيف تدير اتساق التصميم عبر منتج كبير؟", 2),
            ("Describe how you build and maintain a design system.", "صف كيف تبني وتحافظ على نظام تصميم.", 3),
            ("How do you balance aesthetics with usability?", "كيف توازن بين الجماليات وقابلية الاستخدام؟", 2),
        ],
    },

    # ──────────────────────────────────────────
    #  UI/UX Designer
    # ──────────────────────────────────────────
    "UI/UX Designer": {
        "technical": [
            ("How do you use Figma for design collaboration?", "كيف تستخدم Figma للتعاون في التصميم؟", 1),
            ("What is the difference between low-fidelity and high-fidelity wireframes?", "ما الفرق بين النماذج الأولية منخفضة الدقة وعالية الدقة؟", 1),
            ("How do you create an interactive prototype?", "كيف تنشئ نموذجاً أولياً تفاعلياً؟", 2),
            ("What are the WCAG accessibility guidelines you follow?", "ما هي إرشادات WCAG لإمكانية الوصول التي تتبعها؟", 2),
            ("How do you design for different platforms (web, mobile, tablet)?", "كيف تصمم لمنصات مختلفة (ويب، جوال، تابلت)؟", 2),
            ("What is a component library and how do you build one?", "ما هي مكتبة المكونات وكيف تبني واحدة؟", 3),
            ("How do you handle typography in your designs?", "كيف تتعامل مع الخطوط في تصاميمك؟", 2),
            ("What is the role of white space in design?", "ما هو دور المساحة البيضاء في التصميم؟", 2),
            ("How do you design effective navigation systems?", "كيف تصمم أنظمة تنقل فعالة؟", 2),
            ("What is a design handoff and how do you ensure it goes smoothly?", "ما هو تسليم التصميم وكيف تضمن سلاسته؟", 2),
            ("How do you design for dark mode?", "كيف تصمم للوضع الداكن؟", 2),
            ("What is motion design and when do you use it?", "ما هو تصميم الحركة ومتى تستخدمه؟", 3),
            ("How do you conduct A/B testing for design decisions?", "كيف تجري اختبار A/B لقرارات التصميم؟", 3),
            ("What tools do you use for design system documentation?", "ما الأدوات التي تستخدمها لتوثيق نظام التصميم؟", 2),
            ("How do you design forms that minimize user friction?", "كيف تصمم نماذج تقلل من احتكاك المستخدم؟", 2),
        ],
        "behavioral": [
            ("Tell me about a complex design problem you solved.", "أخبرني عن مشكلة تصميم معقدة حللتها.", 3),
            ("How do you handle receiving negative feedback on your designs?", "كيف تتعامل مع تلقي ملاحظات سلبية على تصاميمك؟", 2),
            ("Describe a time you had to design with limited user research.", "صف موقفاً اضطررت فيه للتصميم بأبحاث مستخدم محدودة.", 3),
            ("How do you handle multiple design projects simultaneously?", "كيف تتعامل مع مشاريع تصميم متعددة في وقت واحد؟", 2),
            ("Tell me about a time your design solution was different from what stakeholders expected.", "أخبرني عن موقف كان فيه حل التصميم الخاص بك مختلفاً عما توقعه أصحاب المصلحة.", 3),
            ("How do you ensure design consistency across a product?", "كيف تضمن اتساق التصميم عبر المنتج؟", 2),
            ("Describe a time you had to compromise on your design vision.", "صف موقفاً اضطررت فيه للتنازل عن رؤيتك التصميمية.", 3),
            ("How do you collaborate with UX researchers?", "كيف تتعاون مع باحثي تجربة المستخدم؟", 2),
            ("Tell me about a design that you iterated on many times.", "أخبرني عن تصميم كررت العمل عليه مرات عديدة.", 2),
            ("How do you handle design debt?", "كيف تتعامل مع الدين التصميمي؟", 3),
            ("Describe a time you advocated for accessibility improvements.", "صف موقفاً دافعت فيه عن تحسينات إمكانية الوصول.", 2),
            ("How do you communicate design rationale to stakeholders?", "كيف تنقل مبررات التصميم لأصحاب المصلحة؟", 2),
            ("Tell me about a time you designed for a culture or audience you weren't familiar with.", "أخبرني عن موقف صممت فيه لثقافة أو جمهور لم تكن مألوفاً بهم.", 3),
            ("How do you keep your design portfolio current?", "كيف تبقي محفظة تصاميمك محدثة؟", 1),
            ("Describe how you onboard new designers to follow existing design systems.", "صف كيف تؤهل مصممين جدد لاتباع أنظمة التصميم القائمة.", 2),
        ],
    },

    # ──────────────────────────────────────────
    #  UX Researcher
    # ──────────────────────────────────────────
    "UX Researcher": {
        "technical": [
            ("What is the difference between qualitative and quantitative research?", "ما الفرق بين البحث النوعي والكمي؟", 1),
            ("How do you plan and conduct a usability test?", "كيف تخطط وتجري اختبار قابلية الاستخدام؟", 2),
            ("What are the different types of user interviews?", "ما هي أنواع مقابلات المستخدمين المختلفة؟", 2),
            ("How do you create a research plan?", "كيف تنشئ خطة بحثية؟", 2),
            ("What is a card sorting exercise and when do you use it?", "ما هو تمرين فرز البطاقات ومتى تستخدمه؟", 2),
            ("How do you analyze and synthesize research findings?", "كيف تحلل وتجمع نتائج البحث؟", 3),
            ("What is an affinity diagram and how do you use it?", "ما هو مخطط التقارب وكيف تستخدمه؟", 2),
            ("How do you recruit research participants?", "كيف تجند المشاركين في البحث؟", 2),
            ("What is a journey map and how do you create one from research data?", "ما هي خريطة الرحلة وكيف تنشئ واحدة من بيانات البحث؟", 2),
            ("How do you conduct remote user research?", "كيف تجري بحث المستخدم عن بُعد؟", 2),
            ("What is the System Usability Scale (SUS)?", "ما هو مقياس قابلية استخدام النظام (SUS)؟", 2),
            ("How do you triangulate research findings from different methods?", "كيف تثلث نتائج البحث من طرق مختلفة؟", 3),
            ("What is eye tracking and when is it useful?", "ما هو تتبع العين ومتى يكون مفيداً؟", 3),
            ("How do you measure task success rate and time on task?", "كيف تقيس معدل نجاح المهمة والوقت المستغرق في المهمة؟", 2),
            ("What is diary study methodology?", "ما هي منهجية دراسة المذكرات (Diary Study)؟", 3),
        ],
        "behavioral": [
            ("Tell me about research that challenged assumptions and changed the product direction.", "أخبرني عن بحث تحدى الافتراضات وغيّر اتجاه المنتج.", 3),
            ("How do you handle stakeholders who want to skip research?", "كيف تتعامل مع أصحاب المصلحة الذين يريدون تخطي البحث؟", 3),
            ("Describe a time you had to conduct research with very limited resources.", "صف موقفاً اضطررت فيه لإجراء بحث بموارد محدودة جداً.", 2),
            ("How do you ensure research findings are actionable?", "كيف تضمن أن نتائج البحث قابلة للتنفيذ؟", 2),
            ("Tell me about a time you influenced a major product decision through research.", "أخبرني عن موقف أثرت فيه على قرار منتج كبير من خلال البحث.", 3),
            ("How do you present research findings to different audiences?", "كيف تقدم نتائج البحث لجماهير مختلفة؟", 2),
            ("Describe a research project that didn't go as planned.", "صف مشروعاً بحثياً لم يسر كما هو مخطط.", 2),
            ("How do you build empathy for users across your organization?", "كيف تبني التعاطف مع المستخدمين عبر مؤسستك؟", 2),
            ("Tell me about a time you had to balance speed with research rigor.", "أخبرني عن موقف اضطررت فيه للموازنة بين السرعة ودقة البحث.", 3),
            ("How do you handle conflicting findings from different research methods?", "كيف تتعامل مع نتائج متعارضة من طرق بحث مختلفة؟", 3),
            ("Describe a time you advocated for the user voice in a product decision.", "صف موقفاً دافعت فيه عن صوت المستخدم في قرار منتج.", 2),
            ("How do you maintain participant confidentiality and ethical standards?", "كيف تحافظ على سرية المشاركين والمعايير الأخلاقية؟", 2),
            ("Tell me about a time research revealed an accessibility issue.", "أخبرني عن موقف كشف فيه البحث عن مشكلة في إمكانية الوصول.", 2),
            ("How do you collaborate with designers to turn research into design solutions?", "كيف تتعاون مع المصممين لتحويل البحث إلى حلول تصميمية؟", 2),
            ("Describe how you stay current with UX research methodologies.", "صف كيف تبقى مطلعاً على منهجيات بحث تجربة المستخدم.", 1),
        ],
    },
}


def seed(db: Session | None = None):
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        created_count = 0

        # ── General questions ──
        print("Seeding general questions...")
        for q in GENERAL_QUESTIONS:
            _, created = get_or_create(
                db, Question,
                role_name="general",
                question_text_en=q["en"],
                defaults={
                    "question_text_ar": q["ar"],
                    "question_type": "general",
                    "difficulty": q["difficulty"],
                    "source": "seed",
                    "status": "approved",
                    "original_language": "en",
                },
            )
            if created:
                created_count += 1

        print(f"  General: {created_count} created")

        # ── Role-specific questions ──
        print("Seeding role-specific questions...")
        for role_name, type_map in ROLE_QUESTIONS.items():
            role_count = 0
            for q_type, questions in type_map.items():
                for en_text, ar_text, diff in questions:
                    _, created = get_or_create(
                        db, Question,
                        role_name=role_name,
                        question_text_en=en_text,
                        defaults={
                            "question_text_ar": ar_text,
                            "question_type": q_type,
                            "difficulty": diff,
                            "source": "seed",
                            "status": "approved",
                            "original_language": "en",
                        },
                    )
                    if created:
                        role_count += 1
                        created_count += 1
            print(f"  {role_name}: {role_count} created")

        db.commit()
        print(f"\nSeed complete! Total questions created: {created_count}")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    seed()