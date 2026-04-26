import json
import re
from typing import Any

from fastapi import HTTPException
from openai import OpenAI

from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def _safe_json(raw: str) -> dict:
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No JSON object found")
        return json.loads(raw[start:end + 1])


def _clamp_score(value: float | int) -> int:
    return max(0, min(100, round(float(value))))


def _flatten_skills(skills: dict | list | None) -> list[str]:
    if not skills:
        return []

    if isinstance(skills, list):
        return [str(x).strip() for x in skills if str(x).strip()]

    if isinstance(skills, dict):
        out = []
        for v in skills.values():
            if isinstance(v, list):
                out.extend([str(x).strip() for x in v if str(x).strip()])
        return out

    return []


def build_role_profile(role_name: str, role_description: str | None) -> dict:
    prompt = f"""
Return ONLY valid JSON.

Build a structured hiring profile for this role.

Output shape:
{{
  "must_have_keywords": [],
  "nice_to_have_keywords": [],
  "certifications": [],
  "education_requirements": [],
  "experience_signals": [],
  "hard_requirements": []
}}

Role name: {role_name}
Role description: {role_description or ""}
""".strip()

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {"role": "system", "content": "You are a strict HR role normalizer. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
    )

    try:
        data = _safe_json(resp.choices[0].message.content)
        if not isinstance(data, dict):
            raise ValueError("Role profile is not dict")
    except Exception:
        data = {}

    return {
        "must_have_keywords": data.get("must_have_keywords", []) if isinstance(data.get("must_have_keywords"), list) else [],
        "nice_to_have_keywords": data.get("nice_to_have_keywords", []) if isinstance(data.get("nice_to_have_keywords"), list) else [],
        "certifications": data.get("certifications", []) if isinstance(data.get("certifications"), list) else [],
        "education_requirements": data.get("education_requirements", []) if isinstance(data.get("education_requirements"), list) else [],
        "experience_signals": data.get("experience_signals", []) if isinstance(data.get("experience_signals"), list) else [],
        "hard_requirements": data.get("hard_requirements", []) if isinstance(data.get("hard_requirements"), list) else [],
    }


def _contains_phrase(text: str, phrase: str) -> bool:
    phrase = re.escape(phrase.strip())
    if not phrase:
        return False
    return re.search(rf"\b{phrase}\b", text, flags=re.IGNORECASE) is not None


def score_ats(raw_text: str, extracted_data: dict, role_profile: dict) -> dict:
    text = (raw_text or "").strip()
    text_lower = text.lower()

    contact = (extracted_data or {}).get("contact_info") or {}
    skills = (extracted_data or {}).get("skills") or {}
    experience = (extracted_data or {}).get("experience") or []
    education = (extracted_data or {}).get("education") or []

    issues = []
    format_score = 100

    # ---------- FORMAT / PARSING RUBRIC ----------
    if len(text) < 500:
        format_score -= 30
        issues.append({
            "severity": "high",
            "issue": "Very little text was extracted from the CV.",
            "fix": "Use a text-based PDF or DOCX and avoid scanned-image CVs."
        })

    email_found = bool(contact.get("email")) or bool(re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I))
    if not email_found:
        format_score -= 12
        issues.append({
            "severity": "high",
            "issue": "Email address was not clearly detected.",
            "fix": "Put your email in plain text at the top of the CV."
        })

    phone_found = bool(contact.get("phone")) or bool(re.search(r"(\+?\d[\d\s().-]{7,}\d)", text))
    if not phone_found:
        format_score -= 8
        issues.append({
            "severity": "medium",
            "issue": "Phone number was not clearly detected.",
            "fix": "Use a plain-text phone number in international format."
        })

    headings = ["experience", "education", "skills", "projects", "certifications", "summary", "profile"]
    heading_hits = sum(1 for h in headings if re.search(rf"\b{h}\b", text, re.I))
    if heading_hits < 2:
        format_score -= 15
        issues.append({
            "severity": "high",
            "issue": "Standard section headings were not clearly detected.",
            "fix": "Use clear headings like Summary, Skills, Experience, Education, Projects."
        })

    date_hits = len(re.findall(r"\b(20\d{2}|19\d{2})\b", text))
    if date_hits < 2:
        format_score -= 10
        issues.append({
            "severity": "medium",
            "issue": "Few date values were detected.",
            "fix": "Add clear date ranges for jobs and education."
        })

    if re.search(r"\b\d{1,2}/\d{1,2}/\d{2}\b", text):
        format_score -= 4
        issues.append({
            "severity": "low",
            "issue": "Ambiguous short date format detected.",
            "fix": "Prefer formats like Jan 2024 - Mar 2025 or 2024 - 2025."
        })

    if not experience:
        format_score -= 12
        issues.append({
            "severity": "medium",
            "issue": "No experience entries were extracted.",
            "fix": "Ensure the Experience section is plain text and not inside tables or complex columns."
        })

    flat_skills = _flatten_skills(skills)
    if len(flat_skills) < 5:
        format_score -= 8
        issues.append({
            "severity": "medium",
            "issue": "Few skills were detected.",
            "fix": "Add a dedicated Skills section with clear technical keywords."
        })

    if text.count("|") >= 10:
        format_score -= 12
        issues.append({
            "severity": "high",
            "issue": "Table-like formatting was detected.",
            "fix": "Avoid tables and use a simple single-column layout."
        })

    if re.search(r"\w+\s{6,}\w+", text):
        format_score -= 10
        issues.append({
            "severity": "medium",
            "issue": "Possible multi-column layout detected.",
            "fix": "Use a single-column layout and avoid text boxes."
        })

    format_score = _clamp_score(format_score)

    # ---------- KEYWORD / REQUIREMENTS ----------
    must_have = role_profile.get("must_have_keywords", []) or []
    nice_to_have = role_profile.get("nice_to_have_keywords", []) or []
    certifications = role_profile.get("certifications", []) or []
    education_requirements = role_profile.get("education_requirements", []) or []
    hard_requirements = role_profile.get("hard_requirements", []) or []

    matched_must = [kw for kw in must_have if _contains_phrase(text_lower, kw.lower())]
    missing_must = [kw for kw in must_have if kw not in matched_must]

    matched_nice = [kw for kw in nice_to_have if _contains_phrase(text_lower, kw.lower())]
    missing_nice = [kw for kw in nice_to_have if kw not in matched_nice]

    matched_certs = [kw for kw in certifications if _contains_phrase(text_lower, kw.lower())]
    missing_certs = [kw for kw in certifications if kw not in matched_certs]

    matched_edu = [kw for kw in education_requirements if _contains_phrase(text_lower, kw.lower())]
    missing_edu = [kw for kw in education_requirements if kw not in matched_edu]

    keyword_score = 100

    if must_have:
        coverage = len(matched_must) / len(must_have)
        keyword_score = 40 + (coverage * 40)  # 40..80 from must-have coverage
    else:
        keyword_score = 70

    if nice_to_have:
        keyword_score += (len(matched_nice) / max(len(nice_to_have), 1)) * 10

    if certifications:
        keyword_score += (len(matched_certs) / max(len(certifications), 1)) * 5

    if education_requirements:
        keyword_score += (len(matched_edu) / max(len(education_requirements), 1)) * 5

    keyword_score = _clamp_score(keyword_score)

    hard_requirement_flags = []
    for req in hard_requirements:
        if _contains_phrase(text_lower, str(req).lower()):
            hard_requirement_flags.append({
                "requirement": req,
                "status": "matched",
                "impact": "high"
            })
        else:
            hard_requirement_flags.append({
                "requirement": req,
                "status": "missing",
                "impact": "high"
            })

    ats_score = _clamp_score((format_score * 0.6) + (keyword_score * 0.4))

    checklist = {
        "has_contact_info": email_found or phone_found,
        "has_section_headings": heading_hits >= 2,
        "has_dates": date_hits >= 2,
        "has_bullets": bool(re.search(r"^\s*[-•*]", text, re.M)),
        "likely_tables_or_columns": ("|" in text) or bool(re.search(r"\w+\s{6,}\w+", text)),
        "has_experience": bool(experience),
        "has_education": bool(education),
        "has_skills": len(flat_skills) >= 5,
    }

    return {
        "score": ats_score,
        "format_score": format_score,
        "keyword_score": keyword_score,
        "matched_keywords": {
            "must_have": matched_must,
            "nice_to_have": matched_nice,
            "certifications": matched_certs,
            "education_requirements": matched_edu,
        },
        "missing_keywords": {
            "must_have": missing_must,
            "nice_to_have": missing_nice,
            "certifications": missing_certs,
            "education_requirements": missing_edu,
        },
        "hard_requirement_flags": hard_requirement_flags,
        "issues": issues,
        "checklist": checklist,
    }


def evaluate_role_fit_with_llm(
    raw_text: str,
    extracted_data: dict,
    role_name: str,
    role_description: str | None,
    role_profile: dict,
    language: str,
) -> dict:
    schema = {
        "score": 0,
        "matched_skills": [],
        "missing_skills": [],
        "strengths": [],
        "gaps": [],
        "bullet_rewrites": [{"original": "", "improved": ""}],
        "suggested_keywords": [],
    }

    prompt = f"""
Return ONLY valid JSON.

Evaluate how strong this CV is for the target role.

Output shape:
{json.dumps(schema, ensure_ascii=False)}

Rules:
- Score is integer from 0 to 100
- Be strict, not generous
- Missing skills should be role-relevant
- Bullet rewrites should improve clarity and impact
- Suggested keywords should be practical ATS/job keywords

Language: {language}
Role name: {role_name}
Role description: {role_description or ""}
Role profile: {json.dumps(role_profile, ensure_ascii=False)}

Extracted CV data:
{json.dumps(extracted_data or {}, ensure_ascii=False)}

Raw CV text excerpt:
{(raw_text or '')[:12000]}
""".strip()

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": "You are a strict career evaluator. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
    )

    try:
        data = _safe_json(resp.choices[0].message.content)
        if not isinstance(data, dict):
            raise ValueError("Role fit is not dict")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse role-fit JSON")

    return {
        "score": _clamp_score(data.get("score", 0)),
        "matched_skills": data.get("matched_skills", []) if isinstance(data.get("matched_skills"), list) else [],
        "missing_skills": data.get("missing_skills", []) if isinstance(data.get("missing_skills"), list) else [],
        "strengths": data.get("strengths", []) if isinstance(data.get("strengths"), list) else [],
        "gaps": data.get("gaps", []) if isinstance(data.get("gaps"), list) else [],
        "bullet_rewrites": data.get("bullet_rewrites", []) if isinstance(data.get("bullet_rewrites"), list) else [],
        "suggested_keywords": data.get("suggested_keywords", []) if isinstance(data.get("suggested_keywords"), list) else [],
    }


def build_overall_recommendations(role_fit: dict, ats: dict) -> list[str]:
    recs = []

    for item in ats.get("issues", [])[:3]:
        fix = item.get("fix")
        if fix:
            recs.append(str(fix))

    for gap in role_fit.get("gaps", [])[:2]:
        recs.append(f"Address this gap: {gap}")

    for kw in role_fit.get("suggested_keywords", [])[:3]:
        recs.append(f"Consider adding or naturally reflecting this keyword where relevant: {kw}")

    seen = set()
    deduped = []
    for r in recs:
        x = r.strip()
        if x and x not in seen:
            seen.add(x)
            deduped.append(x)

    return deduped[:6]


def _score_experience_depth(evaluation_json: dict) -> int:
    """Derive experience depth score from extracted data signals."""
    role_fit = evaluation_json.get("role_fit", {})
    ats = evaluation_json.get("ats", {})

    score = 50  # baseline

    # Boost for having experience entries detected
    checklist = ats.get("checklist", {})
    if checklist.get("has_experience"):
        score += 15
    if checklist.get("has_dates"):
        score += 10
    if checklist.get("has_bullets"):
        score += 10

    # Boost from strengths / penalize from gaps
    strengths = role_fit.get("strengths", [])
    gaps = role_fit.get("gaps", [])
    score += min(len(strengths) * 5, 15)
    score -= min(len(gaps) * 3, 10)

    return _clamp_score(score)


def _score_completeness(checklist: dict) -> int:
    """Derive completeness score from ATS checklist."""
    if not checklist:
        return 50

    checks = [
        ("has_contact_info", 20),
        ("has_section_headings", 15),
        ("has_dates", 10),
        ("has_bullets", 10),
        ("has_experience", 15),
        ("has_education", 10),
        ("has_skills", 10),
    ]

    score = 10  # baseline
    for key, weight in checks:
        if checklist.get(key):
            score += weight

    # Penalize tables/columns
    if checklist.get("likely_tables_or_columns"):
        score -= 10

    return _clamp_score(score)


def build_radar_scores(evaluation_json: dict) -> dict:
    """
    Derive 6-dimension radar scores from existing evaluation data.
    No extra AI calls needed — everything comes from role_fit and ats.
    """
    role_fit = evaluation_json.get("role_fit", {})
    ats = evaluation_json.get("ats", {})

    return {
        "ats_compatibility": ats.get("score", 0),
        "skills_relevance": role_fit.get("score", 0),
        "experience_depth": _score_experience_depth(evaluation_json),
        "keyword_coverage": ats.get("keyword_score", 0),
        "format_quality": ats.get("format_score", 0),
        "completeness": _score_completeness(ats.get("checklist", {})),
    }


def run_full_cv_evaluation(
    raw_text: str,
    extracted_data: dict,
    role_name: str,
    role_description: str | None,
    language: str,
) -> dict:
    role_profile = build_role_profile(role_name=role_name, role_description=role_description)

    ats = score_ats(
        raw_text=raw_text,
        extracted_data=extracted_data,
        role_profile=role_profile,
    )

    role_fit = evaluate_role_fit_with_llm(
        raw_text=raw_text,
        extracted_data=extracted_data,
        role_name=role_name,
        role_description=role_description,
        role_profile=role_profile,
        language=language,
    )

    overall_recommendations = build_overall_recommendations(role_fit=role_fit, ats=ats)

    # Build intermediate result for radar score derivation
    eval_data = {
        "role_fit": role_fit,
        "ats": ats,
    }
    radar_scores = build_radar_scores(eval_data)

    return {
        "role_profile": role_profile,
        "role_fit": role_fit,
        "ats": ats,
        "radar_scores": radar_scores,
        "overall_recommendations": overall_recommendations,
    }