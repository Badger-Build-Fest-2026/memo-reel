from fastapi import FastAPI

from app.api.v1.api import api_router
from app.api.v1.endpoints.health import router as health_router

app = FastAPI(title="RecallGraph API", version="0.1.0")
app.include_router(health_router)
app.include_router(api_router, prefix="/api/v1")