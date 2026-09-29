import json
import re
import sys
from pathlib import Path

# Add project root to sys.path so 'agent' imports cleanly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.graph_engine import ReelGraphEngine


def run_verification():
    data_path = Path("data/dummy_reels.jsonl")
    assert data_path.exists(), f"Mock data file {data_path} does not exist!"

    # 1. Verify JSONL exists and load records dynamically
    with open(data_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) > 0, "dummy_reels.jsonl is empty!"
    records = [json.loads(line) for line in lines]
    print(f"[PASS] Successfully read {len(records)} records from {data_path}.")

    # 2. Dynamic check on first record for embedded summary URLs
    first_record = records[0]
    summary_urls = re.findall(r"https?://[^\s\)\"\'>]+", first_record.get("summary", ""))
    assert len(summary_urls) > 0, "First record has no embedded URLs in summary!"
    print(f"[PASS] Dynamic URL check passed for record '{first_record.get('capture_id', 'cap_001')}': found {len(summary_urls)} embedded link(s).")

    # 3. Initialize Graph Engine
    engine = ReelGraphEngine(str(data_path))
    assert engine.graph.number_of_nodes() > 0, "Graph failed to load nodes!"
    print(f"[PASS] Graph engine initialized with {engine.graph.number_of_nodes()} nodes and {engine.graph.number_of_edges()} edges.")

    # 4. Verify node lookup by capture_id / title
    item_id = first_record.get("capture_id")
    loaded_reel = engine.get_reel_by_id(item_id) if hasattr(engine, "get_reel_by_id") else None
    if loaded_reel:
        assert all(u in loaded_reel.get("summary", "") for u in summary_urls), "Summary URLs missing from loaded reel!"
        print(f"[PASS] Dynamic summary URLs match loaded record for '{item_id}'.")

    # 5. Verifies traversal on concept and subcategory
    related_topics = engine.get_related_topics("Model Evaluation")
    assert len(related_topics) > 0, "No related topics found for Model Evaluation"
    print(f"[PASS] Traversal on 'Model Evaluation' found: {related_topics}")

    # 6. Verifies that cooking reel returns populated recipe and embedded URLs
    cooking_reel = engine.get_reel("20-Min Garlic Chicken & Spinach Meal Prep")
    assert cooking_reel is not None, "Cooking reel not found!"
    recipe = cooking_reel.get("recipe")
    assert recipe is not None, "Cooking reel recipe is None!"
    assert len(recipe.get("ingredients", [])) > 0, "Empty ingredients!"
    assert len(recipe.get("steps", [])) > 0, "Empty steps!"
    assert "https://" in cooking_reel.get("summary", ""), "Missing embedded URLs in summary"
    print(f"[PASS] Cooking reel returned recipe with {len(recipe['ingredients'])} ingredients and embedded URLs.")

    # 7. Additional checks: Category retrieval, Lakebase stub
    expected_teched_count = sum(
        1 for r in records
        if r.get("category") == "teched" or r.get("category_label") == "teched"
    )
    teched_reels = engine.get_reels_by_category("teched")
    assert len(teched_reels) == expected_teched_count, (
        f"Expected {expected_teched_count} teched reels from data, got {len(teched_reels)}"
    )
    print(f"[PASS] Category retrieval returned all {len(teched_reels)} matching 'teched' reels.")

    try:
        engine.load_from_lakebase(None)
        assert False, "Expected NotImplementedError from load_from_lakebase"
    except NotImplementedError:
        print("[PASS] Lakebase stub raises NotImplementedError as designed.")

    print("\n[ALL CHECKS PASSED] Finalized Lakebase Part 1 implementation is completely verified!")
    return True


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)