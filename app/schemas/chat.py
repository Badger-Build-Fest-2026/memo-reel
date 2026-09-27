"""
Simplified to match what the real RAG agent (agent/langgraph_agent.py,
run_reel_agent) actually returns: a single markdown string with
citations and Obsidian-style [[wikilinks]] embedded inline - not a
separate structured sources list. There is nothing to put in a
ChatSource - the agent doesn't expose one.
"""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str
    user_id: str  # accepted for forward-compatibility; NOT currently used to
                  # scope results - run_reel_agent queries capture_knowledge
                  # with no user filter, so it answers over every user's
                  # reels pooled together. Fine for a single shared demo
                  # account; worth revisiting before any real multi-user use.


class ChatResponse(BaseModel):
    answer: str  # markdown - render it as markdown client-side, don't display raw
