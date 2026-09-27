"""
Builds a node/edge graph from a user's saved reels, read from the
capture_knowledge table (one JSONB knowledge_json blob per capture,
written by app/services/storage/database_knowledge.py).

  category --- reel --- concept/product/ingredient
                  \
                   --- (another reel sharing that same concept)

Shared concepts across reels are what actually make this a network
rather than a bunch of disconnected stars - if two reels both
mention "Redis", they end up connected through that shared node.

Split into a pure transform (_build_graph_from_rows) and a thin async
DB-querying wrapper (build_graph) so the actual node/edge logic is
unit-testable without a live database connection.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capture_knowledge import CaptureKnowledge
from app.schemas.graph import GraphEdge, GraphNode, GraphResponse, ProductInfo, RecipeInfo


def _concept_id(name: str) -> str:
    return f"concept:{name.strip().lower()}"


def _category_id(category: str) -> str:
    return f"category:{category}"


def _build_graph_from_rows(rows: list[tuple[str, dict, str, str | None]]) -> GraphResponse:
    """
    rows: list of (capture_id, knowledge_json, category, obsidian_url)
    tuples - kept as plain tuples (not ORM rows) so this function has
    no dependency on SQLAlchemy and can be tested in isolation.
    """
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    for capture_id, reel, row_category, row_obsidian_url in rows:
        reel_node_id = f"reel:{capture_id}"
        category = reel.get("category") or row_category
        # the dedicated column is authoritative; knowledge_json's own
        # copy is only a fallback for rows saved before that column existed
        obsidian_url = row_obsidian_url or reel.get("obsidian_url")

        recipe_data = reel.get("recipe")
        product_list_data = reel.get("product_list")

        nodes[reel_node_id] = GraphNode(
            id=reel_node_id,
            label=reel.get("title", "Untitled"),
            type="reel",
            category=category,
            size=1.5,
            reel_url=reel.get("reel_url"),
            summary=reel.get("summary"),
            obsidian_url=obsidian_url,
            recipe=RecipeInfo(**recipe_data) if recipe_data else None,
            product_list=[ProductInfo(**p) for p in product_list_data] if product_list_data else None,
        )

        cat_id = _category_id(category)
        if cat_id not in nodes:
            nodes[cat_id] = GraphNode(id=cat_id, label=category, type="category", size=2.5)
        edges.append(GraphEdge(source=reel_node_id, target=cat_id))

        # (name, description) - concepts and products only. Recipe
        # ingredients deliberately do NOT become graph nodes: unlike a
        # tool or concept, two reels both using "salt" isn't a
        # meaningful connection worth drawing, and a 10-ingredient
        # recipe would otherwise turn every food reel into a dense
        # blob of one-off nodes. The full ingredient list is still
        # available - it's on the reel node itself (recipe field
        # above), shown in its detail panel instead of as satellites.
        named_items: list[tuple[str, str | None]] = []
        if reel.get("concepts"):
            named_items += [
                (c["name"], c.get("description")) for c in reel["concepts"].get("concepts", [])
            ]
        if reel.get("product_list"):
            named_items += [
                (p["name"], p.get("description")) for p in reel["product_list"]
            ]

        for name, description in named_items:
            if not name:
                continue
            cid = _concept_id(name)
            if cid not in nodes:
                nodes[cid] = GraphNode(
                    id=cid, label=name, type="concept", category=category, size=1.0, summary=description
                )
            edges.append(GraphEdge(source=reel_node_id, target=cid))

    return GraphResponse(nodes=list(nodes.values()), edges=edges)


async def build_graph(user_id: str, db: AsyncSession) -> GraphResponse:
    result = await db.execute(
        select(CaptureKnowledge).where(CaptureKnowledge.user_id == user_id)
    )
    rows = result.scalars().all()
    return _build_graph_from_rows(
        [(row.capture_id, row.knowledge_json, row.category, row.obsidian_url) for row in rows]
    )
