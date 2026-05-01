from typing import Any


def build_role_detection_context(structured_cv: dict[str, Any]) -> dict:
    """
    Distils a parsed CV into the minimal context dict that detect_roles() needs.

    Drops: contact_info, links, raw bullets, location, dates.
    Keeps: skills, titles, education, projects, keywords — the signal.
    """
    skills = structured_cv.get("skills", {})
    experience = structured_cv.get("experience", [])
    education = structured_cv.get("education", [])
    projects = structured_cv.get("projects", [])

    # Skills: flatten all buckets, dedupe
    all_skills = list({
        *skills.get("technical", []),
        *skills.get("tools", []),
    })

    # Work history: titles + tech only, cap at 5
    work_history = []
    for exp in experience[:5]:
        entry = {}
        if exp.get("role"):    entry["title"]   = exp["role"]
        if exp.get("company"): entry["company"] = exp["company"]
        if exp.get("tech"):    entry["tech"]    = exp["tech"]
        if entry:
            work_history.append(entry)

    # Education: degree + major, no dates
    edu_summary = []
    for e in education[:3]:
        parts = [p for p in [e.get("degree"), e.get("major")] if p]
        if parts:
            edu_summary.append(" in ".join(parts))

    # Projects: name + tech only
    project_signals = []
    for p in projects[:4]:
        entry = {}
        if p.get("name"): entry["name"] = p["name"]
        if p.get("tech"): entry["tech"] = p["tech"]
        if entry:
            project_signals.append(entry)

    return {
        "source":       "cv",
        "skills":       all_skills,
        "soft_skills":  skills.get("soft", []),
        "work_history": work_history,
        "education":    edu_summary,
        "projects":     project_signals,
        "keywords":     structured_cv.get("keywords", []),
        "summary":      (structured_cv.get("summary") or "")[:300],
        "languages":    structured_cv.get("languages", []),
    }


def cv_has_enough_signal(context: dict) -> bool:
    """
    Returns False if the CV is too sparse for role detection.
    Caller should fall back to questionnaire or show a warning.
    """
    has_skills = len(context.get("skills", [])) >= 2
    has_work_or_edu = (
        bool(context.get("work_history"))
        or bool(context.get("education"))
    )
    return has_skills and has_work_or_edu


def build_profile_prefill(structured_cv: dict[str, Any]) -> dict:
    """
    Extract profile fields from a parsed CV for pre-filling the
    ProfileDetailsPage. Only returns non-empty fields.

    This is used during onboarding (onboarding_complete == false)
    to save the user from re-typing info that's already in their CV.
    """
    prefill: dict[str, Any] = {}
    skills = structured_cv.get("skills", {})
    experience = structured_cv.get("experience", [])
    education = structured_cv.get("education", [])
    projects = structured_cv.get("projects", [])

    # Education → major, university
    if education:
        top_edu = education[0]
        if top_edu.get("major"):
            prefill["major"] = top_edu["major"]
        if top_edu.get("institution"):
            prefill["university"] = top_edu["institution"]
        if top_edu.get("graduation_year"):
            prefill["graduation_year"] = top_edu["graduation_year"]

    # Links
    links = structured_cv.get("links", {})
    if links.get("linkedin"):
        prefill["linkedin_url"] = links["linkedin"]
    if links.get("github"):
        prefill["github_url"] = links["github"]

    # Certifications
    certs = structured_cv.get("certifications", [])
    if certs:
        prefill["certifications"] = [
            {
                "name": c.get("name", ""),
                "issuer": c.get("issuer") or c.get("provider"),
            }
            for c in certs[:10]
            if c.get("name")
        ]

    # Languages
    langs = structured_cv.get("languages", [])
    if langs:
        prefill["languages"] = [
            {"language": l if isinstance(l, str) else l.get("language", ""),
             "level": None if isinstance(l, str) else l.get("level")}
            for l in langs[:8]
        ]

    # Projects — include role and bullet points for CV-quality entries
    if projects:
        prefill["projects"] = [
            {
                "name": p.get("name", ""),
                "role": p.get("role"),           # role the person played on the project
                "description": p.get("description"),
                "tech": p.get("tech", []),
                # bullets: the LLM may return a list of responsibilities
                "bullets": p.get("bullets", []) or p.get("responsibilities", []),
            }
            for p in projects[:8]
            if p.get("name")
        ]

    # Experiences — include description/bullets for richer CV output
    if experience:
        prefill["experiences"] = [
            {
                "role": e.get("role", ""),
                "company": e.get("company", ""),
                "location": e.get("location"),
                "start_date": e.get("start_date"),
                "end_date": e.get("end_date"),
                "description": e.get("description"),
                "bullets": e.get("bullets", []) or e.get("responsibilities", []),
            }
            for e in experience[:8]
            if e.get("role") or e.get("company")
        ]

    # Skills (for the user_skills UI — skill names only, user picks from catalog)
    all_skill_names = list({
        *skills.get("technical", []),
        *skills.get("tools", []),
    })
    if all_skill_names:
        prefill["skill_names"] = all_skill_names[:20]

    return prefill