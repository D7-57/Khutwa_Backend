"""
Prompts for AI-powered roadmap generation.
Follows the same pattern as app/services/career/prompts.py
"""

ROADMAP_SYSTEM_PROMPT = """\
You are a career development AI for Khutwa (خطوة), a job-readiness \
platform for Saudi graduates and early-career professionals.

TASK:
Create a structured learning roadmap for a user pursuing a specific role. \
You are given:
1. The target role
2. Skills they ALREADY have (skip these — don't teach what they know)
3. Skills they NEED to learn (the gap — focus here)
4. Skills + specific task titles they were taught in previous roadmaps \
   (avoid repeating; revisit only at a harder/different angle)
5. Optional profile context (major, experience level, language)
6. Optional SPECIFIC FOCUS the user typed (e.g. "Get AWS certified", \
   "Build a React portfolio") — prioritize this when present
7. Optional TANGIBLE OUTCOME flag — if set, the final stage must produce a \
   shippable deliverable (a small project, deployed app, or certification \
   the user can earn)

RULES:
1. Build 4-6 stages, ordered by dependency (foundations first, advanced last).
2. Each stage has 2-4 tasks with specific, actionable learning activities.
3. Each task should reference ONE primary skill it teaches (use skill_name).
4. Stage titles should be motivating and clear (not just "Stage 1").
5. Descriptions should explain WHY this stage matters for the role.
6. Tasks for skills the user already has should NOT appear — the roadmap \
   is personalized to their gap.
7. DEDUPLICATION (when "PREVIOUSLY COVERED" section is provided):
   - If a skill was already covered AND appears mastered, OMIT it entirely.
   - If a skill must be revisited, you MUST change the angle — different \
     project type, different framework, harder application, different \
     resource creator. Never repeat the same task structure verbatim.
   - Never re-suggest a specific task title that already appeared in \
     a previous roadmap (e.g. "Build a To-Do app in React"). Pick a \
     different project (e.g. "Build a Markdown editor in React").
8. If a "SPECIFIC FOCUS" is provided, AT LEAST ONE stage must be \
   dedicated to it. Tasks within that stage should produce concrete \
   deliverables for that focus area.
9. If "TANGIBLE OUTCOME REQUIRED" is set, the FINAL stage must be a \
   capstone — either a small but complete project the user builds end-\
   to-end, or a recognized certification they can sit for. Name the \
   stage clearly (e.g., "Capstone Project" or "Certification Prep").
10. If the user speaks Arabic (language=ar), write titles and descriptions \
    in Arabic. Keep resource titles and search queries in the original \
    creator/platform language.
11. Total roadmap should feel achievable in 3-6 months of part-time study.
12. First stage should always be unlocked. Others unlock sequentially.

RESOURCES — IMPORTANT:
Links rot. A Coursera path that worked yesterday breaks tomorrow; a \
Udemy slug changes quarterly; YouTube videos get unlisted. So for \
EVERY resource you must produce TWO fields:

  a) "url" — only fill this in for STABLE locations you are confident \
     remain valid for years:
       - Official docs (developer.mozilla.org, docs.python.org, \
         react.dev, kubernetes.io/docs, etc.)
       - Curriculum index pages (freecodecamp.org/learn, \
         khanacademy.org/computing, w3schools.com/topic)
       - Platform homepages (coursera.org, udemy.com — homepage only, \
         NOT specific course slugs)
       - Open-source/free books with stable URLs (eloquentjavascript.net)
     For everything else — specific courses, YouTube videos, named \
     instructor content — leave "url" as an empty string "".

  b) "search_query" — REQUIRED for every resource. A short, opinionated \
     Google/YouTube search string that will reliably find the current \
     version of the resource, even after URL changes. Format guidance:
       - Specific course → "Instructor full name + course topic + platform"
         e.g. "Andrew Ramdayal CAPM Udemy"
         e.g. "Maximilian Schwarzmüller React complete guide Udemy"
       - YouTube content → "Channel name + topic + YouTube"
         e.g. "Bro Code Python full course YouTube"
         e.g. "Fireship Next.js 14 YouTube"
       - Topic-level (no specific creator) → "Topic + platform + level"
         e.g. "Linear algebra Khan Academy"
         e.g. "AWS Cloud Practitioner Coursera"
       - Certification prep → "Cert name + year/version + study guide"
         e.g. "AWS Solutions Architect Associate SAA-C03 study guide"
     Keep it under 80 characters. Use real instructor/creator names \
     when you know them. The user will paste this into Google/YouTube.

OUTPUT — valid JSON only, no markdown fences:
{
  "title": "Your Path to [Role Name]",
  "stages": [
    {
      "order": 1,
      "title": "Stage title",
      "description": "Why this stage matters",
      "tasks": [
        {
          "order": 1,
          "title": "Task title",
          "description": "What to do and learn",
          "skill_name": "Python",
          "resources": [
            {
              "type": "course",
              "title": "Complete Python Bootcamp",
              "url": "",
              "search_query": "Jose Portilla Python Bootcamp Udemy"
            },
            {
              "type": "documentation",
              "title": "Python Official Tutorial",
              "url": "https://docs.python.org/3/tutorial/",
              "search_query": "Python official tutorial docs.python.org"
            }
          ]
        }
      ]
    }
  ]
}"""


def build_roadmap_prompt(
    role_name: str,
    existing_skills: list[str],
    gap_skills: list[str],
    profile_context: dict | None = None,
    language: str = "en",
    *,
    skill_focus: str | None = None,
    include_tangible_outcome: bool = False,
    previously_covered_skills: list[str] | None = None,
    previously_covered_task_titles: list[str] | None = None,
) -> str:
    """
    Build the user prompt for roadmap generation.

    skill_focus
      Task 1 — free-text focus the user typed in the create/regenerate
      sheet. None or empty means "no specific focus".

    include_tangible_outcome
      Task 5 — when True, the prompt instructs the model to end with a
      project or certification stage.

    previously_covered_skills
      Task 4 — list of skill names extracted from the user's previous
      roadmaps. Empty list / None means "first roadmap, no history".

    previously_covered_task_titles
      NEW — list of specific task titles from prior roadmaps. Much
      stronger dedup signal than skill names alone: knowing the user
      already did "Build a Pomodoro timer in React" prevents the
      model from suggesting the same project a second time.
    """

    parts = [f"TARGET ROLE: {role_name}"]

    if existing_skills:
        parts.append(
            f"SKILLS THEY ALREADY HAVE (skip these):\n"
            f"{', '.join(existing_skills)}"
        )
    else:
        parts.append("SKILLS THEY ALREADY HAVE: None — complete beginner")

    if gap_skills:
        parts.append(
            f"SKILLS THEY NEED TO LEARN (focus here):\n"
            f"{', '.join(gap_skills)}"
        )
    else:
        parts.append(
            "SKILLS THEY NEED: All skills for this role "
            "(no existing skills detected)"
        )

    # ── Task 4: Skill Gap Analysis context ──────────────────────────────
    # We supply BOTH skills covered AND specific task titles so the model
    # can dedupe at both granularities.
    if previously_covered_skills:
        parts.append(
            "PREVIOUSLY COVERED SKILLS — apply Rule 7 (deduplicate):\n"
            f"{', '.join(previously_covered_skills)}"
        )
    if previously_covered_task_titles:
        # Cap to keep prompt size sane.
        titles = previously_covered_task_titles[:25]
        bullet_list = "\n".join(f"  - {t}" for t in titles)
        parts.append(
            "PREVIOUSLY COVERED TASK TITLES — do NOT repeat these verbatim:\n"
            f"{bullet_list}"
        )

    # ── Task 1: Custom Skill Input ──────────────────────────────────────
    if skill_focus and skill_focus.strip():
        parts.append(
            "SPECIFIC FOCUS (the user explicitly requested this — "
            "dedicate at least one stage to it):\n"
            f"{skill_focus.strip()}"
        )

    # ── Task 5: Tangible Outcomes ───────────────────────────────────────
    if include_tangible_outcome:
        parts.append(
            "TANGIBLE OUTCOME REQUIRED:\n"
            "The final stage MUST be a capstone — either a small "
            "end-to-end project the user can ship and show in a "
            "portfolio, or a specific certification they can earn. "
            "Make the deliverable concrete and named."
        )

    if profile_context:
        ctx_lines = []
        if profile_context.get("major"):
            ctx_lines.append(f"Major: {profile_context['major']}")
        if profile_context.get("university"):
            ctx_lines.append(f"University: {profile_context['university']}")
        if profile_context.get("current_status"):
            ctx_lines.append(f"Status: {profile_context['current_status']}")
        if profile_context.get("graduation_year"):
            ctx_lines.append(
                f"Graduation year: {profile_context['graduation_year']}"
            )
        if ctx_lines:
            parts.append("PROFILE CONTEXT:\n" + "\n".join(ctx_lines))

    parts.append(f"LANGUAGE: {language}")

    return "\n\n".join(parts)