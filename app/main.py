from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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


# static UI
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_ui():
    return FileResponse(os.path.join("static", "index.html"))