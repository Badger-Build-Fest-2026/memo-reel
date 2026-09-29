"""
POST /chat - answers a query using the real LangGraph RAG agent
(agent/langgraph_agent.py, run_reel_agent), not the earlier
embedding-retrieval prototype this endpoint originally called.

run_reel_agent() is synchronous and can take a while (LangGraph
react-agent loop: multiple tool calls, possibly external URL fetches
via MCP, multiple Gemini calls) - it's offloaded to a thread via
asyncio.to_thread so it doesn't block the event loop while running.

Wire this into the router in app/api/v1/api_endpoints.py:

    from app.api.v1.endpoints.chat import router as chat_router
    api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
"""

import asyncio

from fastapi import APIRouter, HTTPException

from agent.langgraph_agent import run_reel_agent
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        answer = await asyncio.to_thread(run_reel_agent, request.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return ChatResponse(answer=answer)
