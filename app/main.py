from fastapi import FastAPI
from app.routers.health import router as health_router

app = FastAPI(title="Khutwa API")

app.include_router(health_router)

@app.get("/")
def root():
    return {"name": "Khutwa API", "status": "running"}
