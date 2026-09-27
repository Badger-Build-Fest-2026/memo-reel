from typing import Literal

from pydantic import BaseModel

NodeType = Literal["reel", "concept", "category"]


class RecipeInfo(BaseModel):
    ingredients: list[str] = []
    steps: list[str] = []
    servings: str | None = None
    cook_time: str | None = None


class ProductInfo(BaseModel):
    name: str
    description: str
    price: str | None = None
    purchase_link: str | None = None


class GraphNode(BaseModel):
    id: str
    label: str
    type: NodeType
    category: str | None = None   # used for node coloring on the frontend
    size: float = 1.0
    reel_url: str | None = None    # only set for reel nodes
    summary: str | None = None     # only set for reel nodes
    obsidian_url: str | None = None  # only set for reel nodes, if an Obsidian note exists
    recipe: RecipeInfo | None = None          # only set for reel nodes with a recipe
    product_list: list[ProductInfo] | None = None  # only set for reel nodes with products


class GraphEdge(BaseModel):
    source: str
    target: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
