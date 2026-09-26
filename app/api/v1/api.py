from fastapi import APIRouter

from app.api.v1.endpoints.reels import router as reels_router

api_router = APIRouter()
api_router.include_router(reels_router, prefix="/reels", tags=["reels"])