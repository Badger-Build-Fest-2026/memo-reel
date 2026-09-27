"""Decoupled Graph Engine for Instagram Reels Multimodal Knowledge Graph.

Finalized Lakebase 4-Tier Knowledge Graph Topology:
Category -> Subcategory -> Concept -> Reel
With Category Bridges and Cross-Subcategory Bridges.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional
import networkx as nx

CATEGORY_MAP = {
    "food": "Food & Cooking",
    "teched": "Technology & Education",
    "shop": "Shopping & Products",
    "fitness": "Fitness & Health",
    "lifestyle": "Lifestyle & Travel",
    "ent": "Entertainment",
    "other": "Other",
}

# Domain bridges between categories that share conceptual boundaries
CATEGORY_BRIDGES = [
    ("food", "fitness"),    # Nutrition / high protein meals & hypertrophy / health
    ("teched", "shop"),     # Technology & developer tools / software products
]

# Conceptual bridges between subcategories touching related engineering & lifestyle disciplines
SUBCATEGORY_BRIDGES = [
    ("Data Science", "System Design"),   # Production ML pipelines, feature stores & real-time systems
]

# Downward tier ladder, used to enforce ONE-WAY traversal. Topic expansion may
# only move from a lower rank to a higher rank and may NEVER pass through a
# Category anchor. Without this guard, hopping
# (Subcategory) -> (Category) -> (sibling Subcategory) leaks unrelated branches
# into each other's results (e.g. "System Design" surfacing "Data Science").
TIER_ORDER = {"category": 0, "subcategory": 1, "concept": 2, "reel": 3}


class ReelGraphEngine:
    """Graph engine representing multimodal Instagram Reels in an anchor-to-leaf hierarchy."""

    def __init__(self, data_source: Optional[str] = None):
        """Initializes graph and optionally loads records from a data source."""
        self.graph = nx.Graph()
        self.reels: Dict[str, dict] = {}

        if data_source and str(data_source).endswith(".jsonl"):
            self.load_from_jsonl(data_source)

    def load_from_jsonl(self, jsonl_path: str | Path) -> None:
        """Parses each line into a dict and populates the graph."""
        path = Path(jsonl_path)
        if not path.is_file():
            raise FileNotFoundError(f"JSONL file not found: {path}")

        records: List[dict] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                clean_line = line.strip()
                if not clean_line:
                    continue
                records.append(json.loads(clean_line))

        self._populate_graph(records)

    def load_from_lakebase(self, connection_params_or_conn: Any) -> None:
        """Explicit stub ready to connect to Lakebase Postgres with SELECT ... later."""
        # Query pattern:
        # SELECT user_id, capture_id, title, category, category_label, subcategory,
        #        concept, summary, recipe, product_list, link, captions, transcription,
        #        timestamp, obsidian_url FROM reels;
        raise NotImplementedError(
            "Lakebase Postgres connection is not yet configured. Local JSONL data source is supported."
        )

    @staticmethod
    def _node_id(node_type: str, raw_name: str) -> str:
        """Helper to create namespaced node identifiers."""
        return f"{node_type}:{raw_name}"

    def _populate_graph(self, records: List[dict]) -> None:
        """Populates graph from raw reel records keyed by unique link or title."""
        self.graph.clear()
        self.reels.clear()

        for record in records:
            # Key uniquely by link (fallback to title)
            reel_key = record.get("link") or record.get("title")
            if not reel_key:
                continue
            self.reels[reel_key] = record
            # Also store by title for quick lookup
            if record.get("title") and record["title"] != reel_key:
                self.reels[record["title"]] = record

            # 1. Category Node (Anchor)
            cat_code = record.get("category", "other")
            cat_label = record.get("category_label") or CATEGORY_MAP.get(cat_code, cat_code.title())
            cat_node = self._node_id("category", cat_code)
            if not self.graph.has_node(cat_node):
                self.graph.add_node(
                    cat_node,
                    node_type="category",
                    category_code=cat_code,
                    name=cat_label,
                    label=cat_label,
                )

            # 2. Subcategory Node
            subcat_name = record.get("subcategory") or "General"
            subcat_node = self._node_id("subcategory", subcat_name)
            if not self.graph.has_node(subcat_node):
                self.graph.add_node(
                    subcat_node,
                    node_type="subcategory",
                    name=subcat_name,
                    label=subcat_name,
                    category=cat_code,
                )
            # Edge: (Category) -[:HAS_SUBCAT]-> (Subcategory)
            self.graph.add_edge(cat_node, subcat_node, relation="HAS_SUBCAT")

            # 3. Concept Node
            concept_name = record.get("concept") or record.get("title")
            concept_node = self._node_id("concept", concept_name)
            if not self.graph.has_node(concept_node):
                self.graph.add_node(
                    concept_node,
                    node_type="concept",
                    name=concept_name,
                    label=concept_name,
                    subcategory=subcat_name,
                )
            # Edge: (Subcategory) -[:HAS_CONCEPT]-> (Concept)
            self.graph.add_edge(subcat_node, concept_node, relation="HAS_CONCEPT")

            # 4. Reel Node (Leaf)
            reel_node = self._node_id("reel", reel_key)
            self.graph.add_node(
                reel_node,
                node_type="reel",
                id=reel_key,
                name=record.get("title", ""),
                label=record.get("title", ""),
                title=record.get("title", ""),
                url=record.get("link", ""),
                link=record.get("link", ""),
                summary=record.get("summary", ""),
                recipe=record.get("recipe"),
                product_list=record.get("product_list"),
                obsidian_url=record.get("obsidian_url", ""),
                category=cat_code,
                subcategory=subcat_name,
                concept=concept_name,
            )
            # Edge: (Concept) -[:FEATURED_IN]-> (Reel)
            self.graph.add_edge(concept_node, reel_node, relation="FEATURED_IN")

        # 5. Category Bridges: Connect categories that share conceptual boundaries
        for cat_a, cat_b in CATEGORY_BRIDGES:
            node_a = self._node_id("category", cat_a)
            node_b = self._node_id("category", cat_b)
            if self.graph.has_node(node_a) and self.graph.has_node(node_b):
                self.graph.add_edge(node_a, node_b, relation="BRIDGES_TO")

        # 6. Cross-Subcategory Bridges: Connect subcategories touching related disciplines
        for sub_a, sub_b in SUBCATEGORY_BRIDGES:
            node_a = self._node_id("subcategory", sub_a)
            node_b = self._node_id("subcategory", sub_b)
            if self.graph.has_node(node_a) and self.graph.has_node(node_b):
                self.graph.add_edge(node_a, node_b, relation="CROSS_SUBCAT_BRIDGE")

    def get_reel(self, identifier: str) -> Optional[dict]:
        """Returns raw reel record by link or title."""
        if not identifier:
            return None
        # Check direct lookup
        if identifier in self.reels:
            return self.reels[identifier]
        clean = identifier.replace("reel:", "").strip()
        if clean in self.reels:
            return self.reels[clean]
        # Case-insensitive title / link search
        clean_lower = clean.lower()
        for key, reel in self.reels.items():
            if (
                key.lower() == clean_lower
                or reel.get("title", "").lower() == clean_lower
                or reel.get("link", "").lower() == clean_lower
            ):
                return reel
        return None

    def _subcategory_of(self, node: str) -> Optional[str]:
        """Resolve the subcategory node that owns a concept/reel/subcategory node."""
        node_type = self.graph.nodes[node].get("node_type")

        if node_type == "subcategory":
            return node

        if node_type == "concept":
            for neighbor in self.graph.neighbors(node):
                if self.graph.nodes[neighbor].get("node_type") == "subcategory":
                    return neighbor
            return None

        if node_type == "reel":
            # Prefer the attribute recorded at ingest time.
            subcat_name = self.graph.nodes[node].get("subcategory")
            if subcat_name:
                candidate = self._node_id("subcategory", subcat_name)
                if self.graph.has_node(candidate):
                    return candidate
            for neighbor in self.graph.neighbors(node):
                if self.graph.nodes[neighbor].get("node_type") == "concept":
                    return self._subcategory_of(neighbor)
            return None

        return None

    def get_related_topics(self, topic_name: str) -> List[str]:
        """Return topics related to ``topic_name`` by walking strictly DOWNWARD.

        Allowed one-way path (anchor -> leaf)::

            (Category) -> (Subcategory) -> (Concept) -> (Reel)

        Traversal is anchored on exactly one resolved subcategory, so results can
        never bleed across sibling branches. It is FORBIDDEN to climb from a
        Subcategory/Concept up into a Category node, because
        ``(Subcategory) -> (Category) -> (sibling Subcategory)`` links unrelated
        branches (e.g. "System Design" would otherwise surface "Data Science"
        through "Technology & Education").

        Same-tier ``CROSS_SUBCAT_BRIDGE`` edges are intentionally NOT followed
        here: they remain in the graph for visual exploration but must not widen
        retrieval scope.
        """
        normalized = topic_name.strip().lower()
        start_nodes = [
            node
            for node, data in self.graph.nodes(data=True)
            if normalized in str(data.get("name", node)).lower()
            or str(data.get("name", node)).lower() in normalized
        ]
        if not start_nodes:
            return []

        include_anchor = any(
            self.graph.nodes[n].get("node_type") == "category" for n in start_nodes
        )

        # Resolve the anchor subcategory/subcategories, then descend only.
        anchors: List[str] = []
        for node in start_nodes:
            if self.graph.nodes[node].get("node_type") == "category":
                anchors.extend(
                    n
                    for n in self.graph.neighbors(node)
                    if self.graph.nodes[n].get("node_type") == "subcategory"
                )
            else:
                anchor = self._subcategory_of(node)
                if anchor:
                    anchors.append(anchor)

        related: set[str] = set()
        visited: set[str] = set()
        queue = deque(anchors)

        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)

            node_type = self.graph.nodes[node].get("node_type")
            node_tier = TIER_ORDER.get(node_type, -1)

            if include_anchor and node_type == "subcategory":
                related.add(self.graph.nodes[node].get("name", node))

            for neighbor in self.graph.neighbors(node):
                neighbor_type = self.graph.nodes[neighbor].get("node_type")
                neighbor_tier = TIER_ORDER.get(neighbor_type, -1)
                relation = self.graph.edges[node, neighbor].get("relation", "")

                # NEVER climb upward, and NEVER route through a Category anchor.
                if neighbor_type == "category" or neighbor_tier <= node_tier:
                    continue
                # Only follow the canonical downward relations.
                if relation not in ("HAS_CONCEPT", "FEATURED_IN"):
                    continue

                if neighbor_type == "concept":
                    related.add(self.graph.nodes[neighbor].get("name", neighbor))
                queue.append(neighbor)

        return sorted(related)

    def get_reels_by_subcategory(self, subcategory_name: str) -> List[dict]:
        """Return every Reel node belonging to ``subcategory_name``.

        Strict single-subcategory lookup: a reel is returned only when its own
        ``subcategory`` attribute matches exactly (case-insensitive). No sibling
        subcategory lookup and no category-level widening is performed.
        """
        subcat_lower = subcategory_name.strip().lower()
        matched_reels = []
        for node, data in self.graph.nodes(data=True):
            if data.get("node_type") == "reel":
                reel_subcat = data.get("subcategory", "").strip().lower()
                if reel_subcat == subcat_lower:
                    matched_reels.append(data)
        return matched_reels

    def get_reels_by_category(self, category_code_or_name: str) -> List[dict]:
        """Returns all leaf reels under a given category code or label."""
        cat_key = category_code_or_name.strip().lower()
        matched_reels: List[dict] = []
        seen_links = set()

        for reel in self.reels.values():
            link = reel.get("link")
            if link in seen_links:
                continue
            r_cat = reel.get("category", "").lower()
            r_label = reel.get("category_label", "").lower()
            if cat_key in (r_cat, r_label) or cat_key == "all":
                seen_links.add(link)
                matched_reels.append(reel)

        return matched_reels

    def find_node(self, term: str) -> Optional[dict]:
        """Dynamically detect whether a search term matches a Category, Subcategory, or Concept."""
        term_clean = term.strip().lower()
        # Direct exact match
        for node_id, data in self.graph.nodes(data=True):
            node_name = str(data.get("name", "")).strip().lower()
            if term_clean == node_name:
                return {"node_id": node_id, **data}
        
        # Substring / partial match
        for node_id, data in self.graph.nodes(data=True):
            node_name = str(data.get("name", "")).strip().lower()
            if term_clean in node_name or node_name in term_clean:
                return {"node_id": node_id, **data}
        return None

    def get_subtree_reels(self, start_node_id: str) -> List[dict]:
        """Descend strictly downward from start_node_id to collect all leaf reels."""
        if not self.graph.has_node(start_node_id):
            return []

        start_type = self.graph.nodes[start_node_id].get("node_type")
        start_tier = TIER_ORDER.get(start_type, 0)
        
        reels = []
        visited = set()
        queue = deque([start_node_id])

        while queue:
            curr = queue.popleft()
            if curr in visited:
                continue
            visited.add(curr)

            curr_type = self.graph.nodes[curr].get("node_type")
            if curr_type == "reel":
                reel_id = self.graph.nodes[curr].get("id") or self.graph.nodes[curr].get("url")
                reel_obj = self.get_reel(reel_id)
                if reel_obj:
                    reels.append(reel_obj)
                continue

            for neighbor in self.graph.neighbors(curr):
                neighbor_type = self.graph.nodes[neighbor].get("node_type")
                neighbor_tier = TIER_ORDER.get(neighbor_type, -1)
                relation = self.graph.edges[curr, neighbor].get("relation", "")

                # Strictly downward: tier must strictly increase, no ascending, no bridges
                if neighbor_tier > start_tier and relation in ("HAS_SUBCAT", "HAS_CONCEPT", "FEATURED_IN"):
                    queue.append(neighbor)

        return reels
