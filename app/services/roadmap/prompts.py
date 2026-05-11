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
4. Skills they were TAUGHT in previous roadmaps (avoid re-teaching unless \
   their progress shows they haven't actually mastered it)
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
4. Resources must be real, well-known platforms (Coursera, Udemy, YouTube, \
   freeCodeCamp, Khan Academy, MDN, official docs, etc). Use descriptive \
   titles but you may use placeholder URLs if unsure of exact links.
5. Stage titles should be motivating and clear (not just "Stage 1").
6. Descriptions should explain WHY this stage matters for the role.
7. Tasks for skills the user already has should NOT appear — the roadmap \
   is personalized to their gap.
8. If a "PREVIOUSLY COVERED IN PAST ROADMAPS" section is provided, treat \
   those skills as lower-priority — only revisit if necessary to fill a \
   newly identified gap. Do NOT duplicate the same task structure from \
   prior roadmaps; vary the angle (different project, different resource).
9. If a "SPECIFIC FOCUS" is provided, AT LEAST ONE stage must be \
   dedicated to it. Tasks within that stage should produce concrete \
   deliverables for that focus area.
10. If "TANGIBLE OUTCOME REQUIRED" is set, the FINAL stage must be a \
    capstone — either a small but complete project the user builds end-\
    to-end, or a recognized certification they can sit for. Name the \
    stage clearly (e.g., "Capstone Project" or "Certification Prep").
11. If the user speaks Arabic (language=ar), write titles and descriptions \
    in Arabic. Keep resource titles in their original language.
12. Total roadmap should feel achievable in 3-6 months of part-time study.
13. First stage should always be unlocked. Others unlock sequentially.

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
            {"type": "course", "title": "Resource name", "url": "https://..."},
            {"type": "video", "title": "Resource name", "url": "https://..."}
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
    if previously_covered_skills:
        parts.append(
            "PREVIOUSLY COVERED IN PAST ROADMAPS (lower priority — vary "
            "the approach if revisiting):\n"
            f"{', '.join(previously_covered_skills)}"
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