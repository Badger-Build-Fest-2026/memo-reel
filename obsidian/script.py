"""
Pull undelivered rows from capture_knowledge, format each one's already-structured
knowledge_json data (summary, concepts, evidence, links) into an Obsidian-ready
Markdown file, then mark the row delivered and record its obsidian:// URL.

No LLM call is made here -- the extraction pipeline has already produced the
summary/concepts/evidence, so this script just lays that out as Markdown.

Setup:
    pip install "psycopg[binary]" python-dotenv

Usage:
    python reel_captures_to_notes.py --user-id <user_id>                  # every undelivered row for a user
    python reel_captures_to_notes.py --user-id <user_id> --slug <slug>    # just one row, by slug
    python reel_captures_to_notes.py --user-id <user_id> --id <capture_id> # just one row, by id (uuid)
"""

import argparse
import json
import re
import os
from pathlib import Path
import psycopg
from dotenv import load_dotenv

load_dotenv()


CONN_STRING = os.getenv("DATABRICKS_DATABASE_URL")
TABLE_NAME = "capture_knowledge"

VAULT_DIR = Path("./ObsidianVault/Reels")
OBSIDIAN_VAULT_NAME = "Reels"  # must match the name Obsidian shows for this vault
VAULT_SUBPATH = "Reels"                # path inside the vault where notes are written

TITLE_TRUNCATE_LEN = 20  # how many characters of the title to keep in the filename


def sanitize_filename(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9\s-]", "", name)
    name = re.sub(r"[\s-]+", "-", name)
    return name[:150] if name else "untitled"


def make_tags(row: dict) -> list:
    tags = []
    if row.get("category"):
        tags.append(sanitize_filename(row["category"]).lower())
    if row.get("subcategory"):
        tags.append(sanitize_filename(row["subcategory"]).lower())
    # for concept in (row.get("concepts") or {}).get("concepts", []):
    #     if concept.get("name"):
    #         tags.append(sanitize_filename(concept["name"]).lower())
    print(tags)
    return tags


def build_frontmatter(row: dict, tags: list) -> str:
    lines = ["---", f'title: "{row["title"]}"']
    if tags:
        lines.append("tags:")
        lines += [f"  - {t}" for t in tags]
    if row.get("reel_url"):
        lines.append(f'source_url: "{row["reel_url"]}"')
    if row.get("saved_at"):
        lines.append(f"saved: {row['saved_at']}")
    lines.append("---\n")
    return "\n".join(lines)


def format_json_block(value) -> str:
    return f"```json\n{json.dumps(value, indent=2)}\n```\n"


def parse_knowledge(raw) -> dict:
    """knowledge_json may come back as a dict (jsonb) or a JSON-encoded string."""
    if isinstance(raw, str):
        return json.loads(raw)
    return raw or {}


def build_body(row: dict) -> str:
    parts = [f"# {row['title']}\n"]

    if row.get("summary"):
        parts.append(f"{row['summary']}\n")

    concepts = (row.get("concepts") or {}).get("concepts", [])
    if concepts:
        parts.append("## Concepts\n")
        for c in concepts:
            parts.append(f"- **{c.get('name', 'Unnamed')}** — {c.get('description', '')}")
        parts.append("")

    evidence = row.get("evidence") or []
    if evidence:
        parts.append("## Evidence\n")
        for e in evidence:
            ts = e.get("timestamp")
            ts_str = f" (at {ts}s)" if ts is not None else ""
            parts.append(f"- {e.get('claim', '')}{ts_str}")
        parts.append("")

    links = row.get("links") or []
    if links:
        parts.append("## Links\n")
        for link in links:
            desc = link.get("description") or link.get("url")
            parts.append(f"- [{desc}]({link.get('url')})")
        parts.append("")

    if row.get("recipe"):
        parts.append("## Recipe\n")
        parts.append(format_json_block(row["recipe"]))

    if row.get("product_list"):
        parts.append("## Products\n")
        parts.append(format_json_block(row["product_list"]))

    if row.get("caption"):
        parts.append(f"\n> Original caption: {row['caption']}\n")

    return "\n".join(parts)


def build_base_name(row: dict) -> str:
    """firstSubcategoryWord_title(truncated), e.g. tool_useful-op"""
    subcategory_raw = (row.get("subcategory") or "general").strip()
    first_subcategory_word = subcategory_raw.split()[0] if subcategory_raw else "general"
    subcategory = sanitize_filename(first_subcategory_word).lower()

    title_sanitized = sanitize_filename(row.get("title") or "untitled").lower()
    truncated_title = title_sanitized[:TITLE_TRUNCATE_LEN].strip("-") or "untitled"

    return f"{subcategory}_{truncated_title}"


def unique_filepath(base_name: str) -> Path:
    candidate = VAULT_DIR / f"{base_name}.md"
    if not candidate.exists():
        return candidate
    n = 2
    while (VAULT_DIR / f"{base_name}-{n}.md").exists():
        n += 1
    return VAULT_DIR / f"{base_name}-{n}.md"


def build_obsidian_url(filepath: Path) -> str:
    relative = f"{filepath.stem}"
    from urllib.parse import quote
    return f"obsidian://open?vault={quote(OBSIDIAN_VAULT_NAME)}&file={quote(relative)}"


def fetch_undelivered(user_id, slug=None, capture_id=None) -> list:
    query = f"""
        SELECT capture_id, user_id, category, knowledge_json, requested_at,
               delivered_at, obsidian_url
        FROM {TABLE_NAME}
        WHERE delivered_at IS NULL
          AND user_id = %s
    """
    params = [user_id]
    if capture_id:
        query += " AND capture_id = %s"
        params.append(capture_id)

    with psycopg.connect(CONN_STRING) as conn, conn.cursor() as cur:
        cur.execute(query, tuple(params))
        colnames = [d.name for d in cur.description]
        rows = [dict(zip(colnames, row)) for row in cur.fetchall()]

    if slug:
        rows = [r for r in rows if parse_knowledge(r["knowledge_json"]).get("slug") == slug]

    return rows


def mark_delivered(capture_id, obsidian_url: str) -> None:
    with psycopg.connect(CONN_STRING) as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE {TABLE_NAME} SET delivered_at = now(), obsidian_url = %s WHERE capture_id = %s",
            (obsidian_url, capture_id),
        )
        conn.commit()


def main(user_id, slug=None, capture_id=None):
    VAULT_DIR.mkdir(parents=True, exist_ok=True)

    rows = fetch_undelivered(user_id, slug=slug, capture_id=capture_id)
    if not rows:
        print("No undelivered rows found.")
        return

    for row in rows:
        knowledge = parse_knowledge(row["knowledge_json"])
        knowledge.setdefault("category", row.get("category"))
        knowledge.setdefault("saved_at", row.get("requested_at"))

        tags = make_tags(knowledge)
        frontmatter = build_frontmatter(knowledge, tags)
        body = build_body(knowledge)

        base_name = build_base_name(knowledge)
        filepath = unique_filepath(base_name)
        filepath.write_text(frontmatter + body, encoding="utf-8")

        obsidian_url = build_obsidian_url(filepath)
        mark_delivered(row["capture_id"], obsidian_url)

        print(f"Wrote {filepath} -> {obsidian_url}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Obsidian notes from undelivered capture_knowledge rows.")
    parser.add_argument("--user-id", dest="user_id", required=True, help="Only process rows belonging to this user id (uuid)")
    parser.add_argument("--slug", default=None, help="Only process the row with this slug")
    parser.add_argument("--id", dest="capture_id", default=None, help="Only process the row with this id (uuid)")
    args = parser.parse_args()

    main(user_id=args.user_id, slug=args.slug, capture_id=args.capture_id)