from fastapi import APIRouter

from app.api.v1.endpoints.reels import router as reels_router
from app.api.v1.endpoints.health import router as health_router


api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(reels_router, prefix="/reels", tags=["reels"])
