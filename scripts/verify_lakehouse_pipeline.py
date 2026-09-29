"""scripts/verify_lakehouse_pipeline.py - End-to-end Lakehouse pipeline test."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.graph_engine import ReelGraphEngine
from agent.mcp_web_fetcher import enrich_from_web
from agent.tools import ReelAgentTools

LAKEHOUSE_SAMPLE = [
    {
        "capture_id": "27f7235d-3b8b-425e-941a-cbd7ba991b84",
        "user_id": "ce3b433f-ae34-4ad6-b3e4-b68145752e64",
        "requested_at": "2026-09-27 05:22:07.409+00",
        "category": "Technology & Education",
        "knowledge_json": {
            "slug": "web_design_tools",
            "links": [
                {
                    "url": "https://originkit.dev",
                    "description": "Animated UI components",
                },
                {"url": "https://pryzm.design", "description": "Visual studio"},
                {
                    "url": "https://codepen.io",
                    "description": "Particle simulations",
                },
                {
                    "url": "https://ditther.com",
                    "description": "Real-time effects",
                },
            ],
            "title": "Underrated Web Design and Creative Tools",
            "summary": "A roundup of four useful web design tools.",
            "category": "Technology & Education",
            "concepts": {
                "concepts": [
                    {
                        "name": "originkit.dev",
                        "description": "UI components",
                    },
                    {
                        "name": "pryzm.design",
                        "description": "Visual studio",
                    },
                    {
                        "name": "codepen.io",
                        "description": "Code playground",
                    },
                    {
                        "name": "ditther.com",
                        "description": "Visual effects",
                    },
                ]
            },
            "reel_url": "https://www.instagram.com/reel/Dahxs6VoEt1/",
            "subcategory": "Tool Roundup",
        },
    },
    {
        "capture_id": "80b6e735-24c0-4bda-8046-333b52743d06",
        "user_id": "ce3b433f-ae34-4ad6-b3e4-b68145752e64",
        "requested_at": "2026-09-27 05:22:07.409+00",
        "category": "Entertainment",
        "knowledge_json": {
            "slug": "jailer_2_unreleased",
            "links": [],
            "title": "Jailer 2 Unreleased Single Live Performance",
            "summary": "A concert clip showcasing a live performance.",
            "category": "Entertainment",
            "concepts": None,
            "reel_url": "https://www.instagram.com/reel/DdwbF1xBVsS/",
            "subcategory": "Live Performance",
        },
    },
]


def test_pipeline():
  print("--- Testing ReelGraphEngine on Lakehouse schema ---")
  engine = ReelGraphEngine(LAKEHOUSE_SAMPLE)
  assert len(engine.reels) >= 2, "Failed to ingest Lakehouse records"
  print(f"[PASS] Ingested {len(engine.reels)} records.")

  # Check 1: Concepts traversal
  topics = engine.get_related_topics("originkit.dev")
  assert "codepen.io" in topics, f"Expected codepen.io in {topics}"
  print(f"[PASS] Concept traversal: {topics}")

  # Check 2: Clean resources extracted
  cid = "27f7235d-3b8b-425e-941a-cbd7ba991b84"
  resources = engine.get_reel_resources(cid)
  assert len(resources) == 4, f"Expected 4 links, got {len(resources)}"
  print(f"[PASS] Clean resource URLs extracted: {resources}")

  # Check 3: ReelAgentTools verification
  tools = ReelAgentTools(engine, mcp_fetcher=enrich_from_web)
  res = tools.get_external_resources(cid, enrich_via_mcp=False)
  assert len(res["urls"]) == 4, "Tools failed resource lookup"
  print("[PASS] ReelAgentTools retrieved resource URLs.")

  print("\n[ALL PIPELINE CHECKS PASSED]")


if __name__ == "__main__":
  test_pipeline()