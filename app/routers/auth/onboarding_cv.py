"""
POST /auth/onboarding/cv

Accepts a CV file (PDF/DOCX), extracts text, parses structure via LLM,
detects matching roles, and returns profile pre-fill data.

Used during onboarding only (onboarding_complete must be false).
"""

import json
import tempfile
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.career.role import Role
from app.models.profile import Profile
from app.services.career.cv_context_builder import (
    build_role_detection_context,
    build_profile_prefill,
    cv_has_enough_signal,
)
from app.services.career.role_detection import detect_roles

router = APIRouter(prefix="/auth/onboarding", tags=["onboarding-cv"])


# ── Lightweight text extraction (no heavy deps) ──────────────────────────────

def _extract_text_from_pdf(data: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber (if available) or PyPDF2."""
    try:
        import pdfplumber
        import io
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages[:20]]
        return "\n".join(pages).strip()
    except ImportError:
        pass

    try:
        from PyPDF2 import PdfReader
        import io
        reader = PdfReader(io.BytesIO(data))
        pages = [p.extract_text() or "" for p in reader.pages[:20]]
        return "\n".join(pages).strip()
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="No PDF library installed. Install pdfplumber or PyPDF2.",
        )


def _extract_text_from_docx(data: bytes) -> str:
    """Extract text from DOCX bytes."""
    try:
        from docx import Document
        import io
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs).strip()
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="python-docx not installed.",
        )


def _extract_text(filename: str, data: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return _extract_text_from_pdf(data)
    elif ext in ("docx", "doc"):
        return _extract_text_from_docx(data)
    else:
        # Try treating as plain text
        try:
            return data.decode("utf-8", errors="ignore").strip()
        except Exception:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}")


# ── LLM structured CV extraction ─────────────────────────────────────────────

def _llm_extract_structured_cv(raw_text: str) -> dict:
    """
    Use GPT to parse raw CV text into structured JSON.
    Returns a dict with keys: skills, experience, education, projects,
    certifications, languages, links, summary, keywords.
    """
    from openai import OpenAI
    from app.core.config import settings

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    system = """You are a CV parser. Given raw text from a CV/resume, extract structured data.
Return ONLY valid JSON (no markdown fences) with this shape:
{
  "summary": "1-2 sentence professional summary",
  "skills": {
    "technical": ["Python", "React", ...],
    "tools": ["Docker", "AWS", ...],
    "soft": ["leadership", "communication", ...]
  },
  "experience": [
    {
      "role": "Software Engineer",
      "company": "Acme Corp",
      "location": "Riyadh",
      "start_date": "2022-01",
      "end_date": "2024-03",
      "tech": ["Python", "FastAPI"]
    }
  ],
  "education": [
    {
      "degree": "Bachelor's",
      "major": "Computer Science",
      "institution": "King Saud University",
      "graduation_year": 2022
    }
  ],
  "projects": [
    {
      "name": "E-commerce Platform",
      "description": "Built a full-stack e-commerce app",
      "tech": ["React", "Node.js"]
    }
  ],
  "certifications": [
    {"name": "AWS SAA", "issuer": "Amazon"}
  ],
  "languages": [
    {"language": "Arabic", "level": "native"},
    {"language": "English", "level": "fluent"}
  ],
  "links": {
    "linkedin": "https://linkedin.com/in/...",
    "github": "https://github.com/..."
  },
  "keywords": ["machine learning", "cloud", ...]
}
If a section has no data, use empty list/object. Extract what's there, don't invent."""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Parse this CV:\n\n{raw_text[:8000]}"},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
        timeout=30,
    )

    content = resp.choices[0].message.content or "{}"
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        import re
        match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        return {}


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/cv")
async def onboarding_cv_upload(
    cv: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Upload a CV during onboarding. Returns:
    - role_detection: AI-suggested roles from CV content
    - profile_prefill: extracted profile fields to pre-fill the form
    - warning: if CV is too sparse for role detection
    """
    uid = UUID(user_id)

    # Check onboarding state
    profile = db.get(Profile, uid)
    if profile and profile.onboarding_complete:
        raise HTTPException(
            status_code=400,
            detail="Onboarding already complete. Use the profile edit endpoint instead.",
        )

    # Read file
    data = await cv.read()
    if len(data) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10 MB).")

    filename = cv.filename or "cv.pdf"

    # Extract text
    raw_text = _extract_text(filename, data)
    if not raw_text or len(raw_text) < 50:
        raise HTTPException(
            status_code=400,
            detail="Could not extract enough text from the file. Try a different format.",
        )

    # Parse with LLM
    structured = _llm_extract_structured_cv(raw_text)

    # Build role detection context
    cv_context = build_role_detection_context(structured)

    # Detect roles
    role_result = None
    warning = None

    if cv_has_enough_signal(cv_context):
        all_roles = db.query(Role).filter(Role.parent_id.isnot(None)).all()
        if all_roles:
            try:
                role_result = detect_roles(roles=all_roles, context=cv_context)
            except Exception as e:
                warning = f"Role detection failed: {e}"
        else:
            warning = "No roles configured in the system yet."
    else:
        warning = (
            "Your CV didn't have enough detail for automatic role matching. "
            "Please try the questionnaire instead."
        )

    # Build profile pre-fill
    profile_prefill = build_profile_prefill(structured)

    # Save extracted data to profile (only during onboarding)
    if profile is None:
        profile = Profile(id=uid, language="en")
        db.add(profile)

    # Apply non-destructive prefill to profile
    if profile_prefill.get("major") and not profile.major:
        profile.major = profile_prefill["major"]
    if profile_prefill.get("university") and not profile.university:
        profile.university = profile_prefill["university"]
    if profile_prefill.get("linkedin_url") and not profile.linkedin_url:
        profile.linkedin_url = profile_prefill["linkedin_url"]
    if profile_prefill.get("github_url") and not profile.github_url:
        profile.github_url = profile_prefill["github_url"]
    if profile_prefill.get("certifications") and not profile.certifications:
        profile.certifications = profile_prefill["certifications"]
    if profile_prefill.get("languages") and not profile.languages:
        profile.languages = profile_prefill["languages"]
    if profile_prefill.get("projects") and not profile.projects:
        profile.projects = profile_prefill["projects"]
    if profile_prefill.get("experiences") and not profile.experiences:
        profile.experiences = profile_prefill["experiences"]

    try:
        db.commit()
        db.refresh(profile)
    except Exception as e:
        db.rollback()
        debugmsg = f"Profile save failed (non-fatal): {e}"

    return {
        "role_detection": role_result.model_dump() if role_result else None,
        "profile_prefill": profile_prefill,
        "structured_cv": structured,
        "warning": warning,
    }
