import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "cv"

AVAILABLE_TEMPLATES = {
    "classic": {
        "file": "classic.html",
        "name": "Classic",
        "description": "Traditional CV layout with serif font. Summary first, then education.",
    },
    "fresh_graduate": {
        "file": "fresh_graduate.html",
        "name": "Fresh Graduate",
        "description": "Emphasizes projects and education. Ideal for candidates with limited work experience.",
    },
    "ats": {
        "file": "ats.html",
        "name": "ATS Optimized",
        "description": "Clean sans-serif layout. Maximally compatible with applicant tracking systems.",
    },
}

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _clean_text(value) -> str:
    text = str(value or "").strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1].strip()
    if text.endswith(";"):
        text = text[:-1].strip()
    return text


def _normalize_certifications(raw) -> list[str]:
    certs = raw if isinstance(raw, list) else []
    normalized: list[str] = []
    for cert in certs:
        if isinstance(cert, dict):
            name = _clean_text(cert.get("name") or cert.get("title") or cert.get("certification") or "")
            issuer = _clean_text(cert.get("issuer") or "")
            issued = _clean_text(cert.get("issued_date") or cert.get("date") or "")
            cred_id = _clean_text(cert.get("credential_id") or cert.get("id") or "")
            parts = [p for p in [name, issuer, issued] if p]
            text = " - ".join(parts)
            if cred_id:
                text = f"{text} - ID: {cred_id}" if text else f"ID: {cred_id}"
            if text:
                normalized.append(text)
            continue
        text = _clean_text(cert)
        if text:
            normalized.append(text)
    return normalized


def _normalize_languages(raw) -> list[str]:
    langs = raw if isinstance(raw, list) else []
    normalized: list[str] = []
    for lang in langs:
        if isinstance(lang, dict):
            name = _clean_text(lang.get("name") or lang.get("language") or "")
            level = _clean_text(lang.get("level") or "")
            text = f"{name} ({level})" if name and level else (name or level)
            if text:
                normalized.append(text)
            continue
        text = _clean_text(lang)
        if text:
            normalized.append(text)
    return normalized


def _prepare_template_context(cv_data: dict, language: str = "en") -> dict:
    """
    Flatten the cv_data JSON into template-friendly variables.
    Handles missing/None fields gracefully.
    """
    contact = cv_data.get("contact_info") or {}
    skills = cv_data.get("skills") or {}
    experience = cv_data.get("experience") or []
    education = cv_data.get("education") or []
    projects = cv_data.get("projects") or []
    certifications = _normalize_certifications(cv_data.get("certifications"))
    languages_spoken = _normalize_languages(cv_data.get("languages"))

    # normalize skills — could be dict with subcategories or flat list
    if isinstance(skills, dict):
        skills_technical = skills.get("technical") or []
        skills_tools = skills.get("tools") or []
        skills_soft = skills.get("soft") or []
    elif isinstance(skills, list):
        skills_technical = skills
        skills_tools = []
        skills_soft = []
    else:
        skills_technical = []
        skills_tools = []
        skills_soft = []

    # for the classic template, try to split technical skills into subcategories
    # (programming languages, tools/tech, concepts, OS)
    # this is a best-effort split — the template can fall back to a flat list
    programming_languages = []
    tools_tech = []
    concepts = []
    operating_systems = []
    remaining_technical = []

    prog_keywords = {
        "java", "python", "javascript", "typescript", "c", "c++", "c#",
        "go", "kotlin", "swift", "dart", "php", "ruby", "rust", "sql",
        "html", "css", "html/css", "r", "matlab", "scala", "perl",
    }
    os_keywords = {"linux", "windows", "macos", "ubuntu", "unix"}
    concept_keywords = {
        "data structures", "algorithms", "socket programming",
        "oop", "design patterns", "rest", "api", "agile", "scrum",
        "ci/cd", "microservices", "tdd",
    }

    for sk in skills_technical:
        sk_lower = sk.lower().strip()
        if sk_lower in prog_keywords:
            programming_languages.append(sk)
        elif sk_lower in os_keywords:
            operating_systems.append(sk)
        elif sk_lower in concept_keywords or "structures" in sk_lower or "algorithm" in sk_lower:
            concepts.append(sk)
        else:
            remaining_technical.append(sk)

    # merge tools from skills_tools into tools_tech
    tools_tech = list(skills_tools) + [
        sk for sk in remaining_technical
        if sk.lower() not in prog_keywords and sk.lower() not in os_keywords
    ]
    remaining_technical = [
        sk for sk in remaining_technical if sk not in tools_tech
    ]

    # Parse structured links (detect LinkedIn, GitHub)
    raw_links = contact.get("links") or []
    structured_links = []
    for link in raw_links:
        if not link:
            continue
        link_str = str(link).strip()
        lower = link_str.lower()
        url = link_str if link_str.startswith("http") else f"https://{link_str}"
        if "linkedin" in lower:
            structured_links.append({"type": "linkedin", "url": url, "label": "LinkedIn"})
        elif "github" in lower:
            structured_links.append({"type": "github", "url": url, "label": "GitHub"})
        else:
            structured_links.append({"type": "other", "url": url, "label": link_str})

    # Extract job target from keywords or summary
    job_target = cv_data.get("job_target", "") or ""

    return {
        "lang": language,
        "contact": {
            "name": contact.get("name", ""),
            "email": contact.get("email", ""),
            "phone": contact.get("phone", ""),
            "location": contact.get("location", ""),
            "links": raw_links,
            "structured_links": structured_links,
        },
        "job_target": job_target,
        "summary": cv_data.get("summary", ""),
        "experience": experience,
        "education": education,
        "projects": projects,
        "certifications": certifications,
        "languages_spoken": languages_spoken,
        # skills breakdown
        "skills_technical": skills_technical,
        "skills_tools": skills_tools,
        "skills_soft": skills_soft,
        # detailed breakdown for classic template
        "programming_languages": programming_languages,
        "tools_tech": tools_tech,
        "concepts": concepts,
        "operating_systems": operating_systems,
        "remaining_technical": remaining_technical,
    }


def render_cv_html(
    cv_data: dict,
    template_id: str = "classic",
    language: str = "en",
) -> str:
    """
    Render CV data to HTML string using the specified template.
    This same HTML is used for:
    - Frontend live preview (served as HTML)
    - PDF generation (fed to WeasyPrint)
    """
    tmpl_info = AVAILABLE_TEMPLATES.get(template_id)
    if not tmpl_info:
        raise ValueError(f"Unknown template: {template_id}. Available: {list(AVAILABLE_TEMPLATES.keys())}")

    template = _env.get_template(tmpl_info["file"])
    context = _prepare_template_context(cv_data, language)
    return template.render(**context)


def render_cv_pdf(
    cv_data: dict,
    template_id: str = "classic",
    language: str = "en",
) -> bytes:
    """
    Render CV data to PDF bytes.

    Tries WeasyPrint first (best quality, needs system libs like Pango/Cairo).
    Falls back to xhtml2pdf (pure Python, works everywhere including Windows).
    """
    html_string = render_cv_html(cv_data, template_id, language)

    # Try WeasyPrint first (best output quality)
    try:
        from weasyprint import HTML
        return HTML(string=html_string).write_pdf()
    except (ImportError, OSError):
        pass

    # Fallback: xhtml2pdf (pure Python, no system deps)
    try:
        from xhtml2pdf import pisa
        from io import BytesIO

        buffer = BytesIO()
        result = pisa.CreatePDF(html_string, dest=buffer)
        if result.err:
            raise RuntimeError(f"xhtml2pdf error count: {result.err}")
        return buffer.getvalue()
    except ImportError:
        pass

    raise RuntimeError(
        "No PDF engine available. Install either:\n"
        "  - weasyprint (+ system libs: pango, cairo) — best quality\n"
        "  - xhtml2pdf (pure Python, pip install xhtml2pdf) — fallback"
    )


def list_templates() -> list[dict]:
    """Return available template metadata."""
    return [
        {
            "id": tid,
            "name": info["name"],
            "description": info["description"],
        }
        for tid, info in AVAILABLE_TEMPLATES.items()
    ]