"""Verification script for LangGraph Agent and Finalized Lakebase Graph Engine."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.graph_engine import ReelGraphEngine
from agent.langgraph_agent import (
    search_reels,
    get_connected_topics,
    get_reel_details,
    run_reel_agent,
    get_last_agent_error,
    _resolve_subcategory,
    ALL_TOOLS,
)

LIVE_MODE = os.getenv("REELMIND_LIVE", "").strip().lower() in {"1", "true", "yes"}
if not LIVE_MODE:
    os.environ["REELMIND_OFFLINE"] = "1"


def verify_agent() -> bool:
    print("=" * 60)
    print("RUNNING VERIFICATION FOR LAKEBASE GRAPHRAG AGENT")
    print("=" * 60)

    data_path = PROJECT_ROOT / "data" / "dummy_reels.jsonl"
    assert data_path.exists(), f"Dummy data not found at {data_path}"

    # 1. Verifies data/dummy_reels.jsonl
    with data_path.open("r", encoding="utf-8") as f:
        reels = [json.loads(line) for line in f if line.strip()]

    assert len(reels) >= 8, f"Expected at least 8 reels in {data_path}, found {len(reels)}"
    for idx, r in enumerate(reels, 1):
        assert "reel_id" not in r, f"Found deprecated 'reel_id' in record {idx} ({r.get('title')})"
        assert "resources" not in r, f"Found deprecated 'resources' in record {idx} ({r.get('title')})"
        assert "extracted_resources" not in r, f"Found deprecated 'extracted_resources' in record {idx} ({r.get('title')})"
        assert "link" in r and r["link"].startswith("https://www.instagram.com/reel/"), f"Invalid link in record {idx}"
        assert "summary" in r and len(r["summary"]) > 0, f"Missing summary in record {idx}"
        assert "obsidian_url" in r and r["obsidian_url"].startswith("obsidian://open?vault="), f"Invalid obsidian_url in record {idx}"

    print(f"[PASS] data/dummy_reels.jsonl verified: {len(reels)} valid records.")

    # 2. Verifies ReelGraphEngine topology
    engine = ReelGraphEngine(str(data_path))
    node_types = {d.get("node_type") for _, d in engine.graph.nodes(data=True)}
    expected_types = {"category", "subcategory", "concept", "reel"}
    assert node_types == expected_types, f"Unexpected node types: {node_types}"

    edge_relations = {d.get("relation") for _, _, d in engine.graph.edges(data=True)}
    expected_relations = {"HAS_SUBCAT", "HAS_CONCEPT", "FEATURED_IN", "BRIDGES_TO", "CROSS_SUBCAT_BRIDGE"}
    assert expected_relations.issubset(edge_relations), f"Missing edge relations: {expected_relations - edge_relations}"
    print(f"[PASS] ReelGraphEngine 4-tier hierarchy and bridges verified.")

    # 3. Verifies tool definitions
    tool_names = [t.name for t in ALL_TOOLS]
    assert "search_reels" in tool_names
    assert "get_connected_topics" in tool_names
    assert "get_reel_details" in tool_names
    print(f"[PASS] Core agent tools verified: {tool_names}")

    # 4. Verifies "prep me for a data science interview"
    ds_query = "prep me for a data science interview based on my reels"
    print(f"\nExecuting agent query: '{ds_query}'...")
    ds_answer = run_reel_agent(ds_query, data_source=str(data_path))
    assert ds_answer and len(ds_answer.strip()) > 0, "Agent returned empty answer for data science query"
    assert "cross-validation" in ds_answer.lower() or "model evaluation" in ds_answer.lower()
    assert "feature store" in ds_answer.lower() or "feature pipelines" in ds_answer.lower() or "feast" in ds_answer.lower()
    assert "https://www.instagram.com/reel/" in ds_answer
    assert "[@" in ds_answer and "](" in ds_answer
    print("[PASS] Data science interview answer verified.")

    # 5. Verifies "what meal prep recipes did I save"
    meal_query = "what meal prep recipes did I save?"
    print(f"\nExecuting agent query: '{meal_query}'...")
    meal_answer = run_reel_agent(meal_query, data_source=str(data_path))
    assert meal_answer and len(meal_answer.strip()) > 0
    assert "- [ ]" in meal_answer
    assert "https://www.instagram.com/reel/" in meal_answer
    print("[PASS] Meal prep query verified.")

    # 6. Verifies extracted URLs embedded in summary are exposed
    assert "https://" in ds_answer
    assert "https://" in meal_answer
    print("[PASS] Verified embedded URLs from summaries are exposed.")

    # 7. Verifies product list / developer tools query
    cli_query = "show the top developer cli tools list"
    print(f"\nExecuting agent query: '{cli_query}'...")
    cli_answer = run_reel_agent(cli_query, data_source=str(data_path))
    assert "zoxide" in cli_answer.lower() and "ripgrep" in cli_answer.lower()
    assert "https://www.instagram.com/reel/" in cli_answer
    print("[PASS] Developer CLI tools list query verified.")

    # 8. STRICT SUBCATEGORY ISOLATION: graph traversal must never climb upward
    sd_topics = [str(t).lower() for t in get_connected_topics.invoke({"subcategory_or_category": "System Design"})]
    ds_topics = [str(t).lower() for t in get_connected_topics.invoke({"subcategory_or_category": "Data Science"})]
    assert not any("data science" in t for t in sd_topics), f"Traversal leak: System Design -> {sd_topics}"
    assert not any("system design" in t for t in ds_topics), f"Traversal leak: Data Science -> {ds_topics}"
    print("[PASS] get_connected_topics stays downward-only.")

    # 9. STRICT SUBCATEGORY ISOLATION: retrieval scoped
    sd_results = search_reels.invoke({"query": "prep me for a system design interview"})
    assert sd_results, "System Design query returned no reels"
    assert all(r.get("subcategory") == "System Design" for r in sd_results)
    assert _resolve_subcategory("prep me for a system design interview") == "System Design"
    assert _resolve_subcategory("what data science reels do I have") == "Data Science"
    print(f"[PASS] search_reels subcategory scoping verified.")

    # 10. STRICT SUBCATEGORY ISOLATION: zero bleed in end-to-end answer
    sd_answer = run_reel_agent("System Design", data_source=str(data_path))
    assert sd_answer and len(sd_answer.strip()) > 0
    sd_low = sd_answer.lower()
    assert "kafka" in sd_low or "pgvector" in sd_low or "postgres" in sd_low
    bleed_terms = ("cross-validation", "feature store", "feature pipelines", "feast")
    bled = [t for t in bleed_terms if t in sd_low]
    assert not bled, f"System Design answer leaked Data Science content: {bled}"
    assert "https://www.instagram.com/reel/" in sd_answer
    print("[PASS] System Design answer verified free of Data Science bleed.")

    # 11. Category-level downward traversal check
    cat_reels = engine.get_reels_by_category("teched")
    assert len(cat_reels) >= 2, "Category query failed to aggregate subtrees"
    print("[PASS] Category-level downward fanout verified.")

    # 12. Live Gemini LLM check
    if LIVE_MODE:
        assert get_last_agent_error() is None, f"LLM error: {get_last_agent_error()}"
        assert "Degraded mode" not in sd_answer
        print("[PASS] Live Gemini execution succeeded.")
    else:
        print("[SKIP] Live Gemini check skipped (run with REELMIND_LIVE=1 to verify).")

    print("\n[ALL CHECKS PASSED] Finalized Lakebase GraphRAG agent is completely verified!")
    return True


if __name__ == "__main__":
    success = verify_agent()
    sys.exit(0 if success else 1)