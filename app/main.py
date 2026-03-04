from fastapi import FastAPI
from app.routers.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.interviews import router as interviews_router
from app.routers.audio import router as audio_router
from app.routers.cv import router as cv_router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os


app = FastAPI(title="Khutwa API")

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(interviews_router)
app.include_router(audio_router)
app.include_router(cv_router)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_ui():
    return FileResponse(os.path.join("static", "index.html"))

# include your routers as usual
# app.include_router(interviews.router)
# app.include_router(audio.router)
# app.include_router(cv_router)