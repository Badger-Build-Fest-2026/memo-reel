"""Decoupled Graph Engine for Instagram Reels Multimodal Knowledge Graph.

Finalized Lakebase 4-Tier Knowledge Graph Topology:
Category -> Subcategory -> Concept -> Reel
With Category Bridges, Cross-Subcategory Bridges, and Resource Nodes.
"""

from __future__ import annotations

from collections import deque
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import networkx as nx
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

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
    ("food", "fitness"),
    ("teched", "shop"),
]

# Conceptual bridges between subcategories touching related engineering disciplines
SUBCATEGORY_BRIDGES = [
    ("Data Science", "System Design"),
]

TIER_ORDER = {"category": 0, "subcategory": 1, "concept": 2, "reel": 3}

load_dotenv()

class ReelGraphEngine:
  """Graph engine representing multimodal Instagram Reels in an anchor-to-leaf hierarchy."""

  def __init__(self, data_source: Optional[Any] = None):
        """Initializes graph and optionally loads records from a data source."""
        self.graph = nx.Graph()
        self.reels: Dict[str, dict] = {}

        import os
        db_url = data_source if (isinstance(data_source, str) and data_source.startswith("postgres")) else os.getenv("LAKEBASE_DATABASE_URL")

        if db_url and db_url.startswith("postgres"):
            self.load_from_lakebase(db_url)
        elif isinstance(data_source, (str, Path)):
            self.load_from_jsonl(data_source)
        elif isinstance(data_source, list):
            self._populate_graph(data_source)

  def load_from_lakebase(
        self,
        connection_params_or_conn: Any,
        table_name: str = "public.capture_knowledge",
    ) -> None:
        """Connects to Lakebase Postgres and loads all records into the graph."""
        import psycopg2
        from psycopg2.extras import RealDictCursor

        # Handle either a URL connection string or an active connection object
        should_close = False
        if isinstance(connection_params_or_conn, str):
            conn = psycopg2.connect(connection_params_or_conn)
            should_close = True
        elif connection_params_or_conn is not None:
            conn = connection_params_or_conn
        else:
            raise NotImplementedError("Lakebase connection parameter cannot be None.")

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = f"""
                    SELECT capture_id, user_id, requested_at, category, knowledge_json 
                    FROM {table_name} 
                    WHERE knowledge_json IS NOT NULL;
                """
                cur.execute(query)
                raw_records = cur.fetchall()
                print(f"[Lakebase] Successfully pulled {len(raw_records)} rows from {table_name}")

                records = []
                for row in raw_records:
                    rec = dict(row)
                    # Convert stringified JSON to dict if Postgres returned raw text
                    if isinstance(rec.get("knowledge_json"), str):
                        try:
                            rec["knowledge_json"] = json.loads(rec["knowledge_json"])
                        except Exception:
                            pass
                    records.append(rec)

                self._populate_graph(records)
        finally:
            if should_close:
                conn.close()

  @staticmethod
  def _node_id(node_type: str, raw_name: str) -> str:
    return f"{node_type}:{raw_name}"

  def _populate_graph(self, records: List[dict]) -> None:
    self.graph.clear()
    self.reels.clear()

    for raw_record in records:
      kj = raw_record.get("knowledge_json") or {}

      cid = raw_record.get("capture_id")
      title = kj.get("title") or raw_record.get("title", "")
      reel_url = (
          kj.get("reel_url")
          or raw_record.get("link")
          or raw_record.get("reel_url", "")
      )
      cat_code = raw_record.get("category") or kj.get("category", "other")
      subcat_name = (
          kj.get("subcategory")
          or raw_record.get("subcategory")
          or "General"
      )
      summary = kj.get("summary") or raw_record.get("summary", "")
      transcript = (
          kj.get("transcript")
          or raw_record.get("transcription")
          or raw_record.get("transcript", "")
      )
      recipe = kj.get("recipe") or raw_record.get("recipe")
      product_list = kj.get("product_list") or raw_record.get("product_list")
      obsidian_url = raw_record.get("obsidian_url") or kj.get(
          "obsidian_url", ""
      )

      # Extract concepts safely
      raw_concepts_obj = kj.get("concepts") or raw_record.get("concept")
      concept_names: List[str] = []
      if isinstance(raw_concepts_obj, dict):
        c_list = raw_concepts_obj.get("concepts") or []
        concept_names = [
            c["name"] for c in c_list if isinstance(c, dict) and "name" in c
        ]
      elif isinstance(raw_concepts_obj, list):
        concept_names = [
            c if isinstance(c, str) else c.get("name")
            for c in raw_concepts_obj
            if c
        ]
      elif isinstance(raw_concepts_obj, str) and raw_concepts_obj:
        concept_names = [raw_concepts_obj]

      primary_concept = concept_names[0] if concept_names else title

      # Clean resource URLs (handles both [{"url": "..."}] and ["https://..."])
      raw_links = kj.get("links") or raw_record.get("resource_urls") or []
      resource_urls: List[str] = []
      for item in raw_links:
        if isinstance(item, dict) and "url" in item:
          resource_urls.append(item["url"])
        elif isinstance(item, str):
          resource_urls.append(item)

      # Build unified flat record for lookup tools
      normalized_record = {
          "capture_id": cid,
          "title": title,
          "link": reel_url,
          "url": reel_url,
          "category": cat_code,
          "category_label": (
              raw_record.get("category_label")
              or CATEGORY_MAP.get(cat_code, cat_code.title())
          ),
          "subcategory": subcat_name,
          "concept": primary_concept,
          "concepts": concept_names,
          "summary": summary,
          "transcription": transcript,
          "recipe": recipe,
          "product_list": product_list,
          "obsidian_url": obsidian_url,
          "resource_urls": resource_urls,
          "evidence": kj.get("evidence", []),
      }

      primary_key = cid or reel_url or title
      self.reels[primary_key] = normalized_record
      if title and title != primary_key:
        self.reels[title] = normalized_record
      if reel_url and reel_url != primary_key:
        self.reels[reel_url] = normalized_record
      if cid and cid != primary_key:
        self.reels[cid] = normalized_record

      # 1. Category Node
      cat_label = normalized_record["category_label"]
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
      subcat_node = self._node_id("subcategory", subcat_name)
      if not self.graph.has_node(subcat_node):
        self.graph.add_node(
            subcat_node,
            node_type="subcategory",
            name=subcat_name,
            label=subcat_name,
            category=cat_code,
        )
      self.graph.add_edge(cat_node, subcat_node, relation="HAS_SUBCAT")

      # 3. Concept Nodes
      target_concepts = concept_names if concept_names else [primary_concept]
      for c_name in target_concepts:
        if not c_name:
          continue
        c_node = self._node_id("concept", c_name)
        if not self.graph.has_node(c_node):
          self.graph.add_node(
              c_node,
              node_type="concept",
              name=c_name,
              label=c_name,
              subcategory=subcat_name,
          )
        self.graph.add_edge(subcat_node, c_node, relation="HAS_CONCEPT")

      # 4. Reel Node
      reel_node = self._node_id("reel", primary_key)
      self.graph.add_node(
          reel_node, node_type="reel", id=primary_key, **normalized_record
      )

      # Edge from concepts to reel
      for c_name in target_concepts:
        if not c_name:
          continue
        c_node = self._node_id("concept", c_name)
        self.graph.add_edge(c_node, reel_node, relation="FEATURED_IN")

      # 5. Resource Nodes (Clean array for MCP, zero regex)
      for url in resource_urls:
        self.graph.add_node(url, node_type="resource", url=url)
        self.graph.add_edge(reel_node, url, relation="HAS_RESOURCE")

    # Bridges
    for cat_a, cat_b in CATEGORY_BRIDGES:
      node_a = self._node_id("category", cat_a)
      node_b = self._node_id("category", cat_b)
      if self.graph.has_node(node_a) and self.graph.has_node(node_b):
        self.graph.add_edge(node_a, node_b, relation="BRIDGES_TO")

    for sub_a, sub_b in SUBCATEGORY_BRIDGES:
      node_a = self._node_id("subcategory", sub_a)
      node_b = self._node_id("subcategory", sub_b)
      if self.graph.has_node(node_a) and self.graph.has_node(node_b):
        self.graph.add_edge(node_a, node_b, relation="CROSS_SUBCAT_BRIDGE")

  def get_reel(self, identifier: str) -> Optional[dict]:
    if not identifier:
      return None
    if identifier in self.reels:
      return self.reels[identifier]
    clean = identifier.replace("reel:", "").strip()
    if clean in self.reels:
      return self.reels[clean]
    clean_lower = clean.lower()
    for key, reel in self.reels.items():
      if (
          key.lower() == clean_lower
          or reel.get("title", "").lower() == clean_lower
          or reel.get("link", "").lower() == clean_lower
      ):
        return reel
    return None

  def get_reel_by_id(self, capture_id: str) -> Optional[dict]:
    return self.get_reel(capture_id)

  def get_reel_resources(self, identifier: str) -> List[str]:
    """Returns direct clean resource URLs connected via HAS_RESOURCE edges."""
    reel = self.get_reel(identifier)
    if not reel:
      return []

    target_id = (
        reel.get("capture_id") or reel.get("link") or reel.get("title")
    )
    reel_node = self._node_id("reel", target_id)
    if not self.graph.has_node(reel_node):
      return reel.get("resource_urls", [])

    urls = [
        nbr
        for nbr in self.graph.neighbors(reel_node)
        if self.graph.nodes[nbr].get("node_type") == "resource"
    ]
    return urls or reel.get("resource_urls", [])

  def _subcategory_of(self, node: str) -> Optional[str]:
    node_type = self.graph.nodes[node].get("node_type")
    if node_type == "subcategory":
      return node
    if node_type == "concept":
      for neighbor in self.graph.neighbors(node):
        if self.graph.nodes[neighbor].get("node_type") == "subcategory":
          return neighbor
      return None
    if node_type == "reel":
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

        if neighbor_type == "category" or neighbor_tier <= node_tier:
          continue
        if relation not in ("HAS_CONCEPT", "FEATURED_IN"):
          continue

        if neighbor_type == "concept":
          related.add(self.graph.nodes[neighbor].get("name", neighbor))
        queue.append(neighbor)

    return sorted(related)

  def get_reels_by_subcategory(self, subcategory_name: str) -> List[dict]:
    subcat_lower = subcategory_name.strip().lower()
    matched_reels = []
    for _, data in self.graph.nodes(data=True):
      if data.get("node_type") == "reel":
        reel_subcat = data.get("subcategory", "").strip().lower()
        if reel_subcat == subcat_lower:
          matched_reels.append(data)
    return matched_reels

  def get_reels_by_category(self, category_code_or_name: str) -> List[dict]:
    cat_key = category_code_or_name.strip().lower()
    matched_reels: List[dict] = []
    seen = set()

    for reel in self.reels.values():
      uid = reel.get("capture_id") or reel.get("link")
      if uid in seen:
        continue
      r_cat = reel.get("category", "").lower()
      r_label = reel.get("category_label", "").lower()
      if cat_key in (r_cat, r_label) or cat_key == "all":
        seen.add(uid)
        matched_reels.append(reel)

    return matched_reels

  def find_node(self, term: str) -> Optional[dict]:
    term_clean = term.strip().lower()
    for node_id, data in self.graph.nodes(data=True):
      node_name = str(data.get("name", "")).strip().lower()
      if term_clean == node_name:
        return {"node_id": node_id, **data}

    for node_id, data in self.graph.nodes(data=True):
      node_name = str(data.get("name", "")).strip().lower()
      if term_clean in node_name or node_name in term_clean:
        return {"node_id": node_id, **data}
    return None

  def get_subtree_reels(self, start_node_id: str) -> List[dict]:
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
        reel_id = self.graph.nodes[curr].get("id") or self.graph.nodes[
            curr
        ].get("url")
        reel_obj = self.get_reel(reel_id)
        if reel_obj:
          reels.append(reel_obj)
        continue

      for neighbor in self.graph.neighbors(curr):
        neighbor_type = self.graph.nodes[neighbor].get("node_type")
        neighbor_tier = TIER_ORDER.get(neighbor_type, -1)
        relation = self.graph.edges[curr, neighbor].get("relation", "")

        if neighbor_tier > start_tier and relation in (
            "HAS_SUBCAT",
            "HAS_CONCEPT",
            "FEATURED_IN",
        ):
          queue.append(neighbor)

    return reels