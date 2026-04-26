from pydantic import BaseModel, Field, model_validator
from uuid import UUID
from datetime import datetime
from typing import Any


# ── structured CV sub-sections (what the editor form uses) ──


class CVContactInfo(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[str] = []

    # accept extra fields like linkedin, github and put them into links
    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def collect_links(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        links = list(data.get("links") or [])
        for key in ("linkedin", "github", "website", "portfolio"):
            val = data.pop(key, None)
            if val and val not in links:
                links.append(val)
        data["links"] = links
        return data


class CVExperienceItem(BaseModel):
    company: str = ""
    role: str = ""
    start_date: str = ""
    end_date: str = ""
    location: str = ""
    bullets: list[str] = []
    tech: list[str] = []

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        # accept "job_title" as alias for "role"
        if "job_title" in data and not data.get("role"):
            data["role"] = data.pop("job_title")
        # accept "description" as list of bullets
        desc = data.get("description")
        if isinstance(desc, list) and not data.get("bullets"):
            data["bullets"] = desc
            data.pop("description", None)
        elif isinstance(desc, str) and not data.get("bullets"):
            data["bullets"] = [desc] if desc else []
            data.pop("description", None)
        # accept "technologies" as "tech"
        if "technologies" in data and not data.get("tech"):
            data["tech"] = data.pop("technologies")
        return data


class CVEducationItem(BaseModel):
    institution: str = ""
    degree: str = ""
    major: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""

    model_config = {"extra": "allow"}


class CVProjectItem(BaseModel):
    name: str = ""
    description: str = ""
    bullets: list[str] = []
    tech: list[str] = []

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        # accept "technologies" as "tech"
        if "technologies" in data and not data.get("tech"):
            data["tech"] = data.pop("technologies")
        return data


class CVSkills(BaseModel):
    technical: list[str] = []
    tools: list[str] = []
    soft: list[str] = []


# ── full structured CV payload ──


class CVCertificationItem(BaseModel):
    name: str = ""
    issuer: str = ""
    date: str = ""

    model_config = {"extra": "allow"}


class CVLanguageItem(BaseModel):
    name: str = ""
    level: str = ""

    model_config = {"extra": "allow"}


class CVData(BaseModel):
    """The complete CV structure. This is what the editor works with
    and what gets stored in cv_documents.extracted_data.

    Accepts flexible input — skills can be a flat list or structured dict,
    certifications/languages can be strings or objects, etc.
    """
    contact_info: CVContactInfo = CVContactInfo()
    summary: str = ""
    job_target: str = ""
    skills: CVSkills | list[str] = CVSkills()
    experience: list[CVExperienceItem] = []
    education: list[CVEducationItem] = []
    projects: list[CVProjectItem] = []
    certifications: list[CVCertificationItem | str] = []
    languages: list[CVLanguageItem | str] = []
    keywords: list[str] = []

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def normalize_flexible_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # ── skills: accept flat list → put into technical ──
        skills = data.get("skills")
        if isinstance(skills, list):
            data["skills"] = {"technical": skills, "tools": [], "soft": []}

        # ── certifications: accept strings or dicts ──
        certs = data.get("certifications") or []
        normalized_certs = []
        for c in certs:
            if isinstance(c, str):
                normalized_certs.append(c)
            elif isinstance(c, dict):
                # store as string for simplicity: "Name (Issuer, Date)"
                name = c.get("name", "")
                issuer = c.get("issuer", "")
                date = c.get("date", "")
                parts = [name]
                if issuer or date:
                    sub = ", ".join(filter(None, [issuer, date]))
                    parts.append(f"({sub})")
                normalized_certs.append(" ".join(parts))
            else:
                normalized_certs.append(str(c))
        data["certifications"] = normalized_certs

        # ── languages: accept strings or dicts ──
        langs = data.get("languages") or []
        normalized_langs = []
        for l in langs:
            if isinstance(l, str):
                normalized_langs.append(l)
            elif isinstance(l, dict):
                name = l.get("name") or l.get("language", "")
                level = l.get("level", "")
                if level:
                    normalized_langs.append(f"{name} ({level})")
                else:
                    normalized_langs.append(name)
            else:
                normalized_langs.append(str(l))
        data["languages"] = normalized_langs

        return data

    def model_dump(self, **kwargs) -> dict:
        """Override to ensure skills is always stored as a dict."""
        d = super().model_dump(**kwargs)
        if isinstance(d.get("skills"), list):
            d["skills"] = {"technical": d["skills"], "tools": [], "soft": []}
        return d


# ── create from scratch ──


class CVCreateRequest(BaseModel):
    """Create a new CV from the builder (no file upload)."""
    title: str = "My CV"
    language: str = "en"
    cv_data: CVData


class CVCreateResponse(BaseModel):
    cv_id: UUID
    title: str
    language: str
    cv_data: dict
    created_at: datetime

    class Config:
        from_attributes = True


# ── update (save from editor) ──


class CVUpdateRequest(BaseModel):
    """Save current editor state. Only provided fields are updated."""
    title: str | None = None
    language: str | None = None
    cv_data: CVData | None = None


# ── full document response (for loading into editor) ──


class CVBuilderDocumentResponse(BaseModel):
    cv_id: UUID
    title: str | None
    language: str
    cv_data: dict  # the extracted_data JSON
    source: str  # "upload" | "builder"
    created_at: datetime

    class Config:
        from_attributes = True


# ── AI enhance ──


class AIEnhanceRequest(BaseModel):
    """Ask AI to improve a specific section of the CV."""
    section: str  # "summary" | "experience_bullet" | "project_description"
    content: str  # the current text to improve
    context: dict | None = None  # optional: role_name, full cv_data, etc.
    language: str = "en"


class AIEnhanceResponse(BaseModel):
    original: str
    improved: str
    changes_summary: str  # brief explanation of what was changed


# ── preview from raw data (no save) ──


class CVPreviewRequest(BaseModel):
    """Render a preview without saving. Used for live preview."""
    cv_data: CVData
    template: str = "classic"
    language: str = "en"