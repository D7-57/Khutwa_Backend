import json
import uuid
from typing import Tuple

import httpx
from fastapi import HTTPException, UploadFile

from app.core.config import settings
from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def _supabase_storage_upload(
    *,
    bucket: str,
    object_path: str,
    content: bytes,
    content_type: str,
    user_jwt: str,
) -> str:
    """
    Uploads to Supabase Storage using the user's JWT (so RLS applies).
    Returns a storage path that you can store in DB.
    """
    url = f"{settings.SUPABASE_URL}/storage/v1/object/{bucket}/{object_path}"

    headers = {
        "authorization": f"Bearer {user_jwt}",
        "apikey": settings.SUPABASE_ANON_KEY,
        "content-type": content_type or "application/octet-stream",
    }

    r = httpx.post(url, headers=headers, content=content, timeout=30)
    if r.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Supabase upload failed: {r.text}")

    # store as a stable reference (bucket/path). you can generate signed URLs later if needed
    return f"{bucket}/{object_path}"


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader
    from io import BytesIO

    reader = PdfReader(BytesIO(pdf_bytes))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    text = "\n".join(parts).strip()
    return text


def _extract_text_from_docx(docx_bytes: bytes) -> str:
    from docx import Document
    from io import BytesIO

    doc = Document(BytesIO(docx_bytes))
    parts = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    return "\n".join(parts).strip()


def extract_text(file: UploadFile, content: bytes) -> Tuple[str, str]:
    """
    Returns (raw_text, detected_language).
    We keep language simple for v1; you can improve later.
    """
    filename = (file.filename or "").lower()
    mime = (file.content_type or "").lower()

    if filename.endswith(".pdf") or mime == "application/pdf":
        text = _extract_text_from_pdf(content)
        lang = "ar" if any("\u0600" <= ch <= "\u06FF" for ch in text) else "en"
        return text, lang

    if filename.endswith(".docx") or "officedocument.wordprocessingml" in mime:
        text = _extract_text_from_docx(content)
        lang = "ar" if any("\u0600" <= ch <= "\u06FF" for ch in text) else "en"
        return text, lang

    raise HTTPException(status_code=400, detail="Unsupported CV format. Use PDF or DOCX.")


def llm_extract_structured_cv(raw_text: str, language: str) -> dict:
    """
    Uses OpenAI to convert raw CV text into structured JSON.
    """
    schema_hint = {
        "contact_info": {"name": "", "email": "", "phone": "", "location": "", "links": []},
        "summary": "",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experience": [
            {
                "company": "",
                "role": "",
                "start_date": "",
                "end_date": "",
                "location": "",
                "bullets": [],
                "tech": [],
            }
        ],
        "education": [{"institution": "", "degree": "", "major": "", "start_date": "", "end_date": ""}],
        "projects": [{"name": "", "description": "", "bullets": [], "tech": []}],
        "certifications": [],
        "languages": [],
        "keywords": [],
    }

    system = (
        "You are a strict CV parser. Output ONLY valid JSON. "
        "No markdown, no commentary. If a field is unknown, use empty string/empty list."
    )

    user = f"""
Language: {language}
Task: Extract a structured CV JSON from the following raw text.
Return JSON matching this shape exactly (keys may exist even if empty):
{json.dumps(schema_hint, ensure_ascii=False)}

RAW TEXT:
{raw_text[:12000]}
""".strip()

    resp = client.chat.completions.create(
        model="gpt-4o-mini",  # safe default for cost; you can change later
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
    )

    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("Not a JSON object")
        return data
    except Exception:
        # store a minimal fallback rather than failing hard
        return {"raw_parse_error": True, "raw_text_excerpt": raw_text[:2000]}