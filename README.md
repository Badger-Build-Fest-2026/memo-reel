# buildfestproj

## Agent configuration

The GraphRAG agent (`agent/langgraph_agent.py`) resolves a Gemini model id in this
order and tries each one before giving up:

1. `GEMINI_MODEL` (explicit override)
2. `DEFAULT_GEMINI_MODEL` -> `gemini-flash-latest`
3. `FALLBACK_GEMINI_MODEL` -> `gemini-flash-lite-latest` (separate free-tier quota bucket)

> `gemini-1.5-flash` and `gemini-2.5-flash` are closed for this key and return
> `404 NOT_FOUND`. Do not pin them. A failed LLM call is never swallowed: it is logged
> to stderr, recorded in `get_last_agent_error()`, and the reply is prefixed with a
> visible "Degraded mode" banner naming the failing model.

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Credentials; if unset the agent runs on the deterministic graph engine. |
| `GEMINI_MODEL` | Pin the primary model id. |
| `LAKEBASE_DATABASE_URL` | Live Lakebase source; falls back to `data/dummy_reels.jsonl`. |
| `REELMIND_OFFLINE=1` | Force deterministic graph-engine answers (tests / CI / quota safety). |
| `REELMIND_LIVE=1` | `scripts/verify_agent.py` opt-in to exercise the real Gemini call. |

## Retrieval scoping guarantee

A query that names a subcategory is answered **only** from reels in that subcategory:
`_resolve_subcategory()` maps it to one canonical subcategory and `search_reels`
restricts candidates via `ReelGraphEngine.get_reels_by_subcategory()`. Graph traversal
(`get_connected_topics`) walks the 4-tier graph strictly downward
(Category -> Subcategory -> Concept -> Reel), so sibling branches such as
[[System Design]] and [[Data Science]] never bleed into each other.

## Verification

```bash
python scripts/verify_part1.py                   # Lakebase schema + 4-tier graph topology
python scripts/verify_agent.py                   # agent tools + subcategory isolation (offline by default)
REELMIND_LIVE=1 python scripts/verify_agent.py   # same, against the real Gemini model
python scripts/verify_carousel_ui.py             # headless Streamlit AppTest carousel checks
```
