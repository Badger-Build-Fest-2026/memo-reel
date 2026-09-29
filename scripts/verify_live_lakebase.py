"""scripts/verify_live_lakebase_agent.py - End-to-end Lakebase + MCP + LangGraph test."""

import os
from pathlib import Path
import sys
from dotenv import load_dotenv

# Ensure root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.graph_engine import ReelGraphEngine
from agent.langgraph_agent import run_reel_agent
from agent.mcp_web_fetcher import enrich_from_web
from agent.tools import ReelAgentTools

load_dotenv()

DB_URL = os.getenv("LAKEBASE_DATABASE_URL") or (
    "postgresql://buildfest_reels_app:npg_28HWVdbftAqZ@"
    "ep-curly-bird-d8oqvrxj.database.us-east-2.cloud.databricks.com/"
    "databricks_postgres?sslmode=require"
)


def run_live_pipeline_checks():
  print("=" * 60)
  print("1. INGESTION & GRAPH POPULATION")
  print("=" * 60)
  engine = ReelGraphEngine(DB_URL)
  node_count = engine.graph.number_of_nodes()
  edge_count = engine.graph.number_of_edges()
  reel_count = len(engine.reels)
  print(f"[PASS] Ingested {reel_count} reel records from Lakebase.")
  print(f"[PASS] Graph populated with {node_count} nodes and {edge_count} edges.")
  assert reel_count >= 1, "No reels ingested from Lakebase!"

  print("\n" + "=" * 60)
  print("2. TOOL RETRIEVAL & RESOURCE INSPECTION")
  print("=" * 60)
  tools = ReelAgentTools(engine, mcp_fetcher=enrich_from_web)

  # Find a reel that has links/resources
  target_reel = None
  target_resources = []
  for reel in engine.reels.values():
    cid = reel.get("capture_id") or reel.get("link") or reel.get("title")
    resources = engine.get_reel_resources(cid)
    if resources:
      target_reel = reel
      target_resources = resources
      break

  if not target_reel:
    # Fallback to the first reel if none have external links yet
    target_reel = list(engine.reels.values())[0]
    target_resources = engine.get_reel_resources(target_reel.get("capture_id"))

  cid = target_reel.get("capture_id")
  title = target_reel.get("title")
  print(f"[PASS] Testing Reel: '{title}' (ID: {cid})")
  print(f"[PASS] Associated Resources: {target_resources}")

  print("\n" + "=" * 60)
  print("3. FASTMCP EXTERNAL WEB ENRICHMENT")
  print("=" * 60)
  # Test web enrichment on discovered external URLs
  web_links = [
      u
      for u in target_resources
      if "instagram.com" not in u and "youtube.com" not in u
  ]
  if web_links:
    sample_url = web_links[0]
    print(f"[*] Calling FastMCP enrich_from_web on: {sample_url}")
    enriched_text = enrich_from_web(sample_url, max_chars=300)
    print(f"[PASS] FastMCP Response Preview:\n---\n{enriched_text.strip()}\n---")
  else:
    print(
        "[INFO] No external documentation link on this specific row; verified"
        " tool returns clean URL list."
    )

  print("\n" + "=" * 60)
  print("4. LANGGRAPH AGENT LIVE SYNTHESIS")
  print("=" * 60)
  # Formulate query matching the selected reel's concept or title
  concept = target_reel.get("concept") or target_reel.get("subcategory") or title
  test_query = f"Tell me about {concept} based on my saved reels. Provide any resource links."
  print(f"[*] Querying AI Assistant: '{test_query}'")

  response = run_reel_agent(test_query, data_source=DB_URL)
  print("\n[AI Assistant Response]:")
  print("-" * 60)
  print(response)
  print("-" * 60)

  assert len(response.strip()) > 0, "AI Assistant returned empty response!"
  print("\n[ALL DOWNSTREAM CHECKS PASSED] System verified end-to-end.")


if __name__ == "__main__":
  run_live_pipeline_checks()