from typing import Literal

from pydantic import BaseModel

NodeType = Literal["reel", "concept", "category"]


class GraphNode(BaseModel):
    id: str
    label: str
    type: NodeType
    category: str | None = None   # used for node coloring on the frontend
    size: float = 1.0
    reel_url: str | None = None    # only set for reel nodes
    summary: str | None = None     # only set for reel nodes


class GraphEdge(BaseModel):
    source: str
    target: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]