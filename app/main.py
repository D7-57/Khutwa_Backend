from fastapi import FastAPI
from app.routers.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.interviews import router as interviews_router
from app.routers.audio import router as audio_router


app = FastAPI(title="Khutwa API")

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(interviews_router)
app.include_router(audio_router)

@app.get("/")
def root():
    return {"name": "Khutwa API", "status": "running"}
