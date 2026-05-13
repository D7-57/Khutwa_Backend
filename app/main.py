from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from app.db.session import get_db
from app.models.career.role import Role
from app.schemas.career.roles import RoleOut

# ── existing routers ──
from app.routers.health import router as health_router
from app.routers.interviews import router as interviews_router
from app.routers.interview.community import router as community_questions_router
from app.routers.audio import router as audio_router
from app.routers.cv import router as cv_router
from app.routers.cv_quiz import router as cv_quiz_router
from app.routers.cv_dir.builder import router as cv_builder_router


# ── auth / profile / privacy / account ──
from app.routers.auth.profile import router as auth_profile_router
from app.routers.auth.skills import router as auth_skills_router
from app.routers.auth.onboarding_cv import router as onboarding_cv_router
from app.routers.auth.privacy import router as auth_privacy_router
from app.routers.auth.account import router as auth_account_router  # NEW
from app.routers.career.roles import get_role_tree, router as career_roles_router
from app.routers.career.skills import router as career_skills_router
from app.routers.roadmap.roadmap import router as roadmap_router


app = FastAPI(title="Khutwa API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# health
app.include_router(health_router)

# auth & profile
app.include_router(auth_profile_router)
app.include_router(auth_skills_router)
app.include_router(onboarding_cv_router)
app.include_router(auth_privacy_router)
app.include_router(auth_account_router)  # NEW — delete data / delete account / contact update

# career catalog
app.include_router(career_roles_router)
app.include_router(career_skills_router)

# roadmap
app.include_router(roadmap_router)

# existing feature routers
app.include_router(interviews_router)
app.include_router(audio_router)
app.include_router(community_questions_router)
app.include_router(cv_router)
app.include_router(cv_quiz_router)
app.include_router(cv_builder_router)




@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/api/roles/tree", include_in_schema=False)
def compat_api_roles_tree(db: Session = Depends(get_db)):
    """Alias for older/web clients that call `/api/roles/tree`. Canonical route: `GET /career/roles/tree`."""
    return get_role_tree(db)


@app.get("/api/v1/roles", response_model=list[RoleOut], include_in_schema=False)
def compat_api_v1_roles(db: Session = Depends(get_db)):
    """Alias for clients that call `/api/v1/roles` (REST-style). Returns leaf job roles."""
    return (
        db.query(Role)
        .filter(Role.role_type == "role")
        .order_by(Role.name)
        .all()
    )