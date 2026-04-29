from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

# ── existing routers ──
from app.routers.health import router as health_router
from app.routers.interviews import router as interviews_router
from app.routers.interview.community import router as community_questions_router
from app.routers.audio import router as audio_router
from app.routers.cv import router as cv_router
from app.routers.cv_quiz import router as cv_quiz_router
from app.routers.cv_dir.builder import router as cv_builder_router

# ── new organized routers ──
from app.routers.auth.profile import router as auth_profile_router
from app.routers.auth.skills import router as auth_skills_router
from app.routers.career.roles import router as career_roles_router
from app.routers.career.skills import router as career_skills_router


app = FastAPI(title="Khutwa API")

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow the Flutter web app (and any localhost port during dev) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:*",
        "http://127.0.0.1:*",
        # Add your production domain here when deploying, e.g.:
        # "https://khutwa.app",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

# health
app.include_router(health_router)

# auth & profile
app.include_router(auth_profile_router)
app.include_router(auth_skills_router)

# career catalog
app.include_router(career_roles_router)
app.include_router(career_skills_router)

# existing feature routers
app.include_router(interviews_router)
app.include_router(audio_router)
app.include_router(community_questions_router)
app.include_router(cv_router)
app.include_router(cv_quiz_router)
app.include_router(cv_builder_router)


# ── Confirm signup helper ─────────────────────────────────────────────────────
# Called by the Flutter app right after Supabase sign-up when email confirmation
# is enabled and no session is returned. Uses the Supabase Admin API to confirm
# the user so they can log in immediately without checking their email.

class _ConfirmBody(BaseModel):
    user_id: str

@app.post("/auth/confirm-signup")
def confirm_signup(_body: _ConfirmBody):
    """
    Confirms a newly registered Supabase user via the Admin API so the Flutter
    app can sign in immediately without requiring email verification.
    Requires SUPABASE_SERVICE_ROLE_KEY in your .env / environment variables.
    """
    try:
        from supabase import create_client
        from app.core.config import settings

        # Service-role client has admin privileges
        admin = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        admin.auth.admin.update_user_by_id(
            _body.user_id,
            {"email_confirm": True},
        )
        return {"confirmed": True}
    except AttributeError:
        # Older supabase-py versions use a different admin API shape
        raise HTTPException(
            status_code=501,
            detail="confirm-signup requires supabase-py >= 2.x with admin support",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Static UI ─────────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_ui():
    return FileResponse(os.path.join("static", "index.html"))