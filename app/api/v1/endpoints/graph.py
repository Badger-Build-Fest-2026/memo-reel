"""
GET /graph?user_id=... - returns the knowledge graph for the frontend
to render, built from the capture_knowledge table.

Wire this into the router in app/api/v1/api_endpoints.py:

    from app.api.v1.endpoints.graph import router as graph_router
    api_router.include_router(graph_router, prefix="/graph", tags=["graph"])
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.graph import GraphResponse
from app.services.graph.builder import build_graph

router = APIRouter()


@router.get("", response_model=GraphResponse)
async def graph(user_id: str, db: AsyncSession = Depends(get_db)) -> GraphResponse:
    return await build_graph(user_id, db)
