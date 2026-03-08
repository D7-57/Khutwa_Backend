import re
from typing import Any

def score_ats(*, raw_text: str, extracted: dict[str, Any]) -> tuple[int, dict]:
    issues = []
    score = 100

    text = (raw_text or "").strip()
    contact = (extracted or {}).get("contact_info") or {}
    skills = (extracted or {}).get("skills") or {}
    exp = (extracted or {}).get("experience") or []
    edu = (extracted or {}).get("education") or []

    # 1) Parsing quality (big penalties)
    if len(text) < 500:
        score -= 30
        issues.append({"severity":"high","issue":"Very little text extracted (scanner may fail).","fix":"Avoid scanned images; use selectable text PDF or DOCX."})

    # 2) Contact info presence
    if not contact.get("email") and not re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I):
        score -= 12
        issues.append({"severity":"high","issue":"Email not detected clearly.","fix":"Put email in plain text at top (no icons)."})
    if not contact.get("phone") and not re.search(r"(\+?\d[\d\s().-]{7,}\d)", text):
        score -= 8
        issues.append({"severity":"medium","issue":"Phone number not detected clearly.","fix":"Use international format +966... in plain text."})

    # 3) Section headings
    headings = ["experience","education","skills","projects","certifications","summary","profile"]
    heading_hits = sum(1 for h in headings if re.search(rf"\b{h}\b", text, re.I))
    if heading_hits < 2:
        score -= 15
        issues.append({"severity":"high","issue":"Missing standard section headings.","fix":"Use clear headings: Summary, Skills, Experience, Education, Projects."})

    # 4) Dates (ATS likes consistent dates)
    date_hits = len(re.findall(r"\b(20\d{2}|19\d{2})\b", text))
    if date_hits < 2:
        score -= 10
        issues.append({"severity":"medium","issue":"Few/no dates detected.","fix":"Add date ranges per job/education (e.g., 2023–2025)."})
    # bad date formats sometimes
    if re.search(r"\b\d{1,2}/\d{1,2}/\d{2}\b", text):  # like 1/2/23
        score -= 4
        issues.append({"severity":"low","issue":"Ambiguous date format detected.","fix":"Prefer 'Jan 2023 – Mar 2024' or '2023 – 2024'."})

    # 5) Experience presence
    if not exp:
        score -= 12
        issues.append({"severity":"medium","issue":"No experience items extracted.","fix":"Ensure Experience section is text, not in a table/2-column layout."})

    # 6) Skills presence
    flat_skills = []
    if isinstance(skills, dict):
        for v in skills.values():
            if isinstance(v, list): flat_skills += v
    if len(flat_skills) < 5:
        score -= 8
        issues.append({"severity":"medium","issue":"Few skills detected.","fix":"Add a dedicated Skills section with comma/bullet list."})

    # 7) Layout red flags (tables/columns/icons often break ATS)
    # Heuristics: lots of pipes, repeated big spacing, bullet symbols ok but excessive columns not.
    if text.count("|") >= 10:
        score -= 12
        issues.append({"severity":"high","issue":"Table-like formatting detected (|).","fix":"Avoid tables; use simple single-column text."})
    if re.search(r"\w+\s{6,}\w+", text):  # suspicious multi-column spacing
        score -= 10
        issues.append({"severity":"medium","issue":"Possible multi-column layout detected.","fix":"Use single-column layout; avoid text boxes."})

    # clamp
    score = max(0, min(100, score))

    checklist = {
        "has_contact_info": bool(contact.get("email") or contact.get("phone")),
        "has_section_headings": heading_hits >= 2,
        "has_dates": date_hits >= 2,
        "has_experience": bool(exp),
        "has_skills": len(flat_skills) >= 5,
        "layout_red_flags": any(i["severity"] in ["medium","high"] and "layout" in i["issue"].lower() for i in issues),
    }

    return score, {"score": score, "issues": issues, "checklist": checklist}