"""agent/tools.py - Internal Graph Tools and External MCP Bridge."""

from typing import Any, Callable, Dict, List, Optional
from agent.graph_engine import ReelGraphEngine


class ReelAgentTools:

  def __init__(
      self,
      engine: ReelGraphEngine,
      mcp_fetcher: Optional[Callable[[str], str]] = None,
  ):
    self.engine = engine
    self.mcp_fetcher = mcp_fetcher

  def search_by_concept(self, concept_name: str) -> Dict[str, Any]:
    """Finds related concepts and reels matching a concept name."""
    related = self.engine.get_related_topics(concept_name)
    matched_reels = []
    seen = set()

    for reel in self.engine.reels.values():
      uid = reel.get("capture_id") or reel.get("link")
      if uid in seen:
        continue

      concepts = reel.get("concepts") or [reel.get("concept")]
      if any(
          concept_name.lower() in str(c).lower() for c in concepts if c
      ) or (concept_name.lower() in reel.get("title", "").lower()):
        seen.add(uid)
        matched_reels.append(reel)

    return {
        "concept": concept_name,
        "related_topics": related,
        "matched_reels": matched_reels,
    }

  def inspect_reel(self, identifier: str) -> Optional[Dict[str, Any]]:
    """Fetches full reel payload including recipe and raw resource URLs."""
    reel = self.engine.get_reel(identifier)
    if not reel:
      return None

    resources = self.engine.get_reel_resources(
        reel.get("capture_id") or reel.get("link") or identifier
    )
    reel_copy = dict(reel)
    reel_copy["graph_resources"] = resources
    return reel_copy

  def get_external_resources(
      self, identifier: str, enrich_via_mcp: bool = False
  ) -> Dict[str, Any]:
    """Retrieves clean resource URLs for a reel, optionally enriching documentation via MCP."""
    reel = self.inspect_reel(identifier)
    if not reel:
      return {"identifier": identifier, "urls": [], "enrichment": {}}

    urls = reel.get("graph_resources") or []
    results = {"identifier": identifier, "urls": urls, "enrichment": {}}

    if enrich_via_mcp and self.mcp_fetcher:
      for url in urls:
        if "instagram.com" not in url and "youtube.com" not in url:
          try:
            results["enrichment"][url] = self.mcp_fetcher(url)
          except Exception as e:
            results["enrichment"][url] = f"MCP Fetch Error: {str(e)}"

    return results

  def list_category_knowledge(
      self, category_key: str
  ) -> List[Dict[str, Any]]:
    """Retrieves all reels indexed under a broad category."""
    return self.engine.get_reels_by_category(category_key)