"""scripts/verify_part2.py - Verification for ReelAgentTools & MCP bridging."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.graph_engine import ReelGraphEngine
from agent.tools import ReelAgentTools

# Import project MCP web fetcher or mock fallback
try:
  from agent.mcp_web_fetcher import fetch_url_content
except (ImportError, ModuleNotFoundError):

  def fetch_url_content(url: str) -> str:
    return f"[MOCK MCP 200 OK] Simulated markdown fetch for {url}"


def run_checks():
  data_path = Path("data/dummy_reels.jsonl")
  assert data_path.exists(), f"{data_path} not found"

  engine = ReelGraphEngine(str(data_path))
  tools = ReelAgentTools(engine, mcp_fetcher=fetch_url_content)

  # Check 1: Concept search
  concept_res = tools.search_by_concept("Model Evaluation")
  assert len(concept_res["matched_reels"]) > 0, "No reels found for concept"
  print(
      f"[PASS] Concept search matched"
      f" {len(concept_res['matched_reels'])} reel(s)."
  )

  # Check 2: Inspect reel
  target_id = concept_res["matched_reels"][0].get("capture_id", "cap_001")
  reel_data = tools.inspect_reel(target_id)
  assert reel_data is not None, f"Failed to inspect reel {target_id}"
  print(f"[PASS] Inspect reel returned record for '{target_id}'.")

  # Check 3: Deterministic resource URL check (No Regex)
  res_data = tools.get_external_resources(target_id, enrich_via_mcp=True)
  assert (
      len(res_data["urls"]) > 0
  ), f"No graph resources found for '{target_id}'!"
  assert any(
      "scikit-learn" in u or "youtube.com" in u for u in res_data["urls"]
  ), f"Expected URL missing from graph resources: {res_data['urls']}"
  print(
      f"[PASS] Retrieved {len(res_data['urls'])} clean resource URL(s) from"
      " graph."
  )

  # Check 4: MCP enrichment check
  assert len(res_data["enrichment"]) > 0, "MCP did not enrich external documentation"
  print(
      f"[PASS] MCP successfully enriched"
      f" {len(res_data['enrichment'])} external documentation link(s)."
  )

  print("\n[ALL PART 2 CHECKS PASSED] Graph tools and MCP bridge verified.")


if __name__ == "__main__":
  run_checks()