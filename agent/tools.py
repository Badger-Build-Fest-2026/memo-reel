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
    """Finds related entities and matched reels by concept name."""
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
    """Fetches full reel payload including raw links and graph resources."""
    reel = self.engine.get_reel(identifier)
    if not reel:
      return None

    resources = self.engine.get_reel_resources(
        reel.get("capture_id") or reel.get("link") or identifier
    )
    reel_copy = dict(reel)
    reel_copy["graph_resources"] = resources
    return reel_copy

  def enrich_links(
      self, identifier: str, max_chars_per_link: int = 1500
  ) -> Dict[str, Any]:
    """Inspects the 'links' list of a reel, visits each web page via MCP,

    and returns extracted page summaries for context enrichment.
    """
    reel = self.inspect_reel(identifier)
    if not reel:
      return {"identifier": identifier, "links": [], "enrichment": {}}

    raw_links = reel.get("links") or []
    # If links are dicts with url/description or simple string urls
    extracted_urls = []
    for item in raw_links:
      if isinstance(item, dict) and "url" in item:
        extracted_urls.append(item["url"])
      elif isinstance(item, str):
        extracted_urls.append(item)

    if not extracted_urls:
      extracted_urls = reel.get("graph_resources") or []

    enrichment_summaries = {}
    if self.mcp_fetcher:
      for url in extracted_urls:
        if "instagram.com" not in url and "youtube.com" not in url:
          try:
            content = self.mcp_fetcher(url)
            # Clip cleanly to serve as a focused external summary
            enrichment_summaries[url] = content[:max_chars_per_link].strip()
          except Exception as exc:
            enrichment_summaries[url] = f"Error enriching {url}: {exc}"

    return {
        "identifier": identifier,
        "links": raw_links,
        "extracted_urls": extracted_urls,
        "enrichment": enrichment_summaries,
    }

  def list_category_knowledge(
      self, category_key: str
  ) -> List[Dict[str, Any]]:
    """Retrieves all reels indexed under a broad category."""
    return self.engine.get_reels_by_category(category_key)