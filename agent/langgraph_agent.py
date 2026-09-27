"""LangGraph Agent Engine for Instagram Reels Multimodal Knowledge Graph.

Finalized Lakebase Schema:
Category -> Subcategory -> Concept -> Reel
"""
from __future__ import annotations

import os
import re
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Suppress fixed-sampling notices
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_google_genai")

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from agent.graph_engine import ReelGraphEngine

# Load environment variables
load_dotenv()

_LAKEBASE_URL = os.getenv("LAKEBASE_DATABASE_URL")
_DEFAULT_DATA_SOURCE = _LAKEBASE_URL if _LAKEBASE_URL else "data/dummy_reels.jsonl"

_engine_instance: Optional[ReelGraphEngine] = None

# Most recent LLM failure reason. Exposed via get_last_agent_error() so a broken
# LLM path is diagnosable instead of silently degrading.
_LAST_AGENT_ERROR: Optional[str] = None

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
FALLBACK_GEMINI_MODEL = "gemini-2.5-flash-lite"

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

_RESOLVED_WORKING_MODEL: Optional[str] = None


def find_working_gemini_model(api_key: str) -> Optional[str]:
    """Test candidate models sequentially and return the first working model ID.
    
    Caches the working model so probe queries run only once per session.
    """
    global _RESOLVED_WORKING_MODEL
    if _RESOLVED_WORKING_MODEL:
        return _RESOLVED_WORKING_MODEL

    # Priority list based on your AI Studio quota dashboard:
    # 1. Custom env override (if specified)
    # 2. High-quota / low-usage Lite endpoints (500 RPD)
    # 3. Fallbacks
    candidates = [
        os.getenv("GEMINI_MODEL"),
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-2.5-flash",
        "gemini-3.8-flash",
    ]

    # De-duplicate while preserving priority order
    seen = set()
    ordered_candidates = [m for m in candidates if m and not (m in seen or seen.add(m))]

    print("[ReelMind] Probing available Gemini models for active quota...", file=sys.stderr)

    for candidate in ordered_candidates:
        try:
            test_llm = ChatGoogleGenerativeAI(
                model=candidate,
                google_api_key=api_key,
                temperature=0.0,
                max_retries=0,  # Fail fast without waiting on backoffs
            )
            # Lightweight test invocation
            test_llm.invoke([HumanMessage(content="ping")])
            print(f"[ReelMind] Model selected and ready: {candidate}", file=sys.stderr)
            _RESOLVED_WORKING_MODEL = candidate
            return candidate
        except Exception as exc:
            err_msg = str(exc)
            if "ResourceExhausted" in err_msg or "429" in err_msg or "RateLimit" in err_msg:
                reason = "Quota / Rate Limit Exceeded"
            elif "404" in err_msg or "NotFound" in err_msg:
                reason = "Model endpoint not found"
            else:
                reason = type(exc).__name__
            print(f"  [-] {candidate}: {reason}", file=sys.stderr)

    return None


def get_graph_engine(data_source: Optional[str] = None) -> ReelGraphEngine:
    """Singleton getter / loader for ReelGraphEngine instance."""
    global _engine_instance
    if _engine_instance is None or (data_source and data_source != getattr(_engine_instance, "_current_source", None)):
        source = data_source or _DEFAULT_DATA_SOURCE
        _engine_instance = ReelGraphEngine(source)
        setattr(_engine_instance, "_current_source", source)
    return _engine_instance


def _offline_mode_forced() -> bool:
    """True when deterministic offline mode is requested (tests / CI)."""
    return os.getenv("REELMIND_OFFLINE", "").strip().lower() in {"1", "true", "yes"}


def get_last_agent_error() -> Optional[str]:
    """Return why the last LLM call failed, or None when it succeeded."""
    return _LAST_AGENT_ERROR


SYSTEM_PROMPT = """You are ReelMind, an expert multimodal knowledge retrieval assistant specialized in Instagram Reels knowledge graphs.

Follow these strict guidelines when formulating answers:
1. Ground every factual assertion directly in data retrieved from your tools.
2. Sourced citations MUST cite the Instagram Reel URL using this exact markdown link format:
   [@title or author](link)  (where link is the Instagram reel URL, e.g. https://www.instagram.com/reel/...)
3. Extract and display any external URLs found inside the `summary` string (such as GitHub repos, docs, YouTube videos, or Google maps) as clean markdown links: [Resource Description](url).
4. Format every key category, subcategory, and concept in Obsidian wikilinks: [[Category]], [[Subcategory]], and [[Concept]].
5. If recipes or meal prep ingredients are discussed or requested:
   - Format ingredients as checklist checkboxes:
     - [ ] ingredient item
   - List step-by-step cooking instructions clearly with numbered steps.
6. For product lists or ranked CLI tools (product_list), render a clean numbered list:
   1. product_name
7. Append an Obsidian vault link at the end of reel notes when available:
   [Open in Obsidian](obsidian_url)
8. For situational queries (e.g. "prep me for a data science interview"), expand only WITHIN the subcategory the question names: stay inside [[Data Science]] (e.g. [[Model Evaluation]], [[Feature Pipelines]]) and never pull in reels from a sibling subcategory such as [[System Design]].
9. STRICT SUBCATEGORY ISOLATION: when the user names a subcategory (for example [[System Design]], [[Data Science]], [[High Protein Meals]], [[Hypertrophy]], [[Productivity]], or [[Japan Travel]]), answer ONLY from reels whose subcategory matches. Never mix sibling subcategories, and never substitute a category-level answer for the subcategory that was actually requested.
"""

# Common stopwords to exclude from term expansion scoring
STOPWORDS = {"prep", "me", "for", "a", "an", "the", "in", "on", "of", "and", "or", "based", "my", "reels", "what", "show", "did", "i", "save", "saved"}

# Canonical subcategory of every reel in the graph. A query resolves to at most
# ONE subcategory, so retrieval can never widen across sibling branches.
SUBCATEGORY_ALIASES = {
    "data science": "Data Science",
    "machine learning": "Data Science",
    "mlops": "Data Science",
    "feature store": "Data Science",
    "feature stores": "Data Science",
    "feature pipelines": "Data Science",
    "model evaluation": "Data Science",
    "cross-validation": "Data Science",
    "system design": "System Design",
    "distributed systems": "System Design",
    "kafka": "System Design",
    "consumer lag": "System Design",
    "vector search": "System Design",
    "pgvector": "System Design",
    "hnsw": "System Design",
    "high protein meals": "High Protein Meals",
    "meal prep": "High Protein Meals",
    "recipe": "High Protein Meals",
    "hypertrophy": "Hypertrophy",
    "strength training": "Hypertrophy",
    "progressive overload": "Hypertrophy",
    "productivity": "Productivity",
    "developer tools": "Productivity",
    "terminal workflow": "Productivity",
    "cli": "Productivity",
    "japan travel": "Japan Travel",
    "kyoto": "Japan Travel",
    "travel": "Japan Travel",
}

# Subcategory-SCOPED synonyms. Expansion may only draw from the vocabulary of the
# subcategory the query already resolved to: a "system design" query must never
# expand to "feast", which belongs to Data Science.
SUBCATEGORY_SYNONYMS = {
    "Data Science": ["data science", "cross-validation", "out-of-time splits", "temporal drift", "model evaluation", "scikit-learn", "feature store", "feature pipelines", "feast", "mlops"],
    "System Design": ["system design", "distributed systems", "kafka", "consumer lag", "partition", "offset", "pgvector", "hnsw", "vector search", "postgres", "postgresql", "indexing"],
    "High Protein Meals": ["meal prep", "garlic chicken", "chicken", "spinach", "high protein", "quinoa", "recipe"],
    "Hypertrophy": ["hypertrophy", "progressive overload", "strength", "volume", "muscle", "workout"],
    "Productivity": ["productivity", "cli", "terminal", "developer tools", "ripgrep", "fzf", "zoxide", "eza", "bat", "rust"],
    "Japan Travel": ["japan travel", "kyoto", "temples", "cafes", "itinerary", "travel"],
}


def _resolve_subcategory(query: str) -> Optional[str]:
    """Resolve a free-text query to exactly one canonical subcategory name.

    The longest matching alias wins, so "high protein meals" beats the shorter
    "meal prep" when that exact phrase is present. Returns None when the query
    names no known subcategory, in which case retrieval stays unscoped.
    """
    q_lower = query.lower()
    for alias in sorted(SUBCATEGORY_ALIASES, key=len, reverse=True):
        if alias in q_lower:
            return SUBCATEGORY_ALIASES[alias]
    return None


def _extract_urls(text: str) -> List[str]:
    """Helper to extract http/https URLs from text."""
    if not text:
        return []
    url_pattern = r"https?://[^\s,\)\]]+"
    return re.findall(url_pattern, text)


@tool
def search_reels(query: str) -> List[Dict[str, Any]]:
    """Search for relevant reels by matching keywords across title, transcription, captions, summary, subcategory, and concept.

    Returns top matches with title, url (link), summary, subcategory, concept.
    """
    # NOTE: When connecting to Databricks Lakebase Postgres, replace keyword scoring with:
    # SELECT user_id, capture_id, title, category, category_label, subcategory,
    #        concept, summary, recipe, product_list, link, captions, transcription,
    #        timestamp, obsidian_url
    # FROM reels
    # ORDER BY embedding <=> query_vec
    # LIMIT 5;

    engine = get_graph_engine()
    q_lower = query.lower()

    # Extract base tokens excluding generic stopwords
    raw_tokens = set(re.findall(r"\w+", q_lower))
    informative_tokens = {t for t in raw_tokens if t not in STOPWORDS and len(t) > 2}

    # --- STRICT SUBCATEGORY SCOPING ----------------------------------------
    # When the query names a subcategory, the candidate pool is confined to that
    # exact subcategory via ReelGraphEngine.get_reels_by_subcategory(). We never
    # widen to sibling subcategories, so a [[System Design]] question cannot
    # surface [[Data Science]] reels (and vice versa).
    resolved_subcategory = _resolve_subcategory(query)

    if resolved_subcategory:
        scoped_nodes = engine.get_reels_by_subcategory(resolved_subcategory)
        allowed_links = {(node.get("link") or node.get("url")) for node in scoped_nodes}
        candidate_reels = [
            reel
            for reel in engine.reels.values()
            if (reel.get("link") or reel.get("url")) in allowed_links
        ]
        # Synonyms may only come from the resolved subcategory's own vocabulary.
        expanded_terms = set(informative_tokens) | set(
            SUBCATEGORY_SYNONYMS.get(resolved_subcategory, [])
        )
    else:
        candidate_reels = list(engine.reels.values())
        expanded_terms = set(informative_tokens)

    # De-duplicate: engine.reels is intentionally keyed by both link and title.
    unique_candidates = []
    seen_links = set()
    for reel in candidate_reels:
        link = reel.get("link") or reel.get("url")
        if link in seen_links:
            continue
        seen_links.add(link)
        unique_candidates.append(reel)

    scored_reels = []

    for reel in unique_candidates:
        title = reel.get("title", "")
        summary = reel.get("summary", "")
        captions = reel.get("captions", "")
        transcription = reel.get("transcription", "")
        subcategory = reel.get("subcategory", "")
        concept = reel.get("concept", "")
        category = reel.get("category", "")
        cat_label = reel.get("category_label", "")

        text_corpus = f"{title} {concept} {subcategory} {summary} {captions} {transcription} {category} {cat_label}".lower()

        score = 0
        for term in expanded_terms:
            t_lower = term.lower()
            if t_lower in title.lower():
                score += 10
            if t_lower in concept.lower():
                score += 9
            if t_lower in subcategory.lower():
                score += 8
            if t_lower in summary.lower():
                score += 5
            if t_lower in transcription.lower():
                score += 3
            if t_lower in captions.lower():
                score += 2
            elif t_lower in text_corpus:
                score += 1

        if score > 0:
            scored_reels.append((score, reel))

    scored_reels.sort(key=lambda x: x[0], reverse=True)
    if not scored_reels:
        # Stay inside the resolved scope: never widen to other subcategories.
        scored_reels = [(0, r) for r in unique_candidates]

    results = []
    for score, r in scored_reels[:5]:
        results.append({
            "title": r.get("title"),
            "url": r.get("link"),
            "link": r.get("link"),
            "summary": r.get("summary"),
            "subcategory": r.get("subcategory"),
            "concept": r.get("concept"),
            "category": r.get("category"),
            "category_label": r.get("category_label"),
            "recipe": r.get("recipe"),
            "product_list": r.get("product_list"),
            "obsidian_url": r.get("obsidian_url"),
        })
    return results


@tool
def get_connected_topics(subcategory_or_category: str) -> List[str]:
    """Return topics related to a subcategory/category/concept, walking the graph strictly DOWNWARD.

    Only follows (Category) -> (Subcategory) -> (Concept) -> (Reel). Upward hops through a
    Category node are forbidden, so results never leak into sibling subcategories (for example
    [[System Design]] never returns [[Data Science]]).
    """
    engine = get_graph_engine()
    return engine.get_related_topics(subcategory_or_category)


@tool
def get_reel_details(reel_title_or_link: str) -> Dict[str, Any]:
    """Fetch complete reel details including embedded summary links, recipe, and product list."""
    engine = get_graph_engine()
    reel = engine.get_reel(reel_title_or_link)
    if not reel:
        return {"error": f"Reel '{reel_title_or_link}' not found."}

    summary = reel.get("summary", "")
    extracted_urls = _extract_urls(summary)

    return {
        "title": reel.get("title"),
        "url": reel.get("link"),
        "link": reel.get("link"),
        "category": reel.get("category"),
        "category_label": reel.get("category_label"),
        "subcategory": reel.get("subcategory"),
        "concept": reel.get("concept"),
        "summary": summary,
        "summary_embedded_urls": extracted_urls,
        "recipe": reel.get("recipe"),
        "product_list": reel.get("product_list"),
        "obsidian_url": reel.get("obsidian_url"),
    }

@tool
def explore_topic_hierarchy(query_term: str) -> Dict[str, Any]:
    """Examine if a topic exists in the knowledge graph. 
    Returns the node level (category, subcategory, concept) and all descendant reels strictly downward.
    """
    engine = get_graph_engine()
    node = engine.find_node(query_term)
    if not node:
        return {"found": False, "message": f"No category, subcategory, or concept matches '{query_term}'."}

    node_id = node["node_id"]
    node_type = node.get("node_type")
    reels = engine.get_subtree_reels(node_id)

    return {
        "found": True,
        "matched_node": node.get("name"),
        "tier": node_type,
        "leaf_reels_count": len(reels),
        "reels": reels[:6],  # Pass top leaves for grounding
    }


ALL_TOOLS = [search_reels, get_connected_topics, get_reel_details, explore_topic_hierarchy]

def _model_candidates() -> List[str]:
    """Return verified working Gemini models in fallback order."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    probed_model = find_working_gemini_model(api_key) if api_key else None

    raw_candidates = [
        probed_model,
        os.getenv("GEMINI_MODEL"),
        DEFAULT_GEMINI_MODEL,
        FALLBACK_GEMINI_MODEL,
        "gemini-flash-lite-latest",
    ]

    ordered: List[str] = []
    for model in raw_candidates:
        if model and model not in ordered:
            ordered.append(model)
    return ordered


def create_agent(google_api_key: Optional[str] = None, model_name: Optional[str] = None):
    """Initializes the LangGraph ReAct agent using the dynamically verified model."""
    api_key = google_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None

    # Resolve working candidate if not explicitly forced
    selected_model = model_name or find_working_gemini_model(api_key)
    if not selected_model:
        return None

    llm = ChatGoogleGenerativeAI(
        model=selected_model,
        temperature=0.2,
        google_api_key=api_key,
    )
    return create_react_agent(llm, ALL_TOOLS, prompt=SYSTEM_PROMPT)


def _dynamic_fallback_runner(query: str) -> str:
    """Dynamic fallback runner that inspects matching concepts without hardcoded text templates."""
    engine = get_graph_engine()
    search_results = search_reels.invoke({"query": query})

    if not search_results:
        return "No relevant reels found in the knowledge graph. Try exploring categories like [[Technology & Education]] or [[Food & Cooking]]."

    recipe_reels = [r for r in search_results if r.get("recipe")]
    product_reels = [r for r in search_results if r.get("product_list")]

    q_lower = query.lower()

    # 1. Specialized recipe response if user asks for recipe/ingredients
    if any(k in q_lower for k in ["recipe", "ingredient", "cook", "chicken", "meal prep"]) and recipe_reels:
        r = recipe_reels[0]
        title = r.get("title", "")
        link = r.get("url") or r.get("link", "")
        subcat = r.get("subcategory", "")
        concept = r.get("concept", "")
        cat_label = r.get("category_label", "Food & Cooking")
        summary = r.get("summary", "")
        recipe = r.get("recipe", {})
        obs_url = r.get("obsidian_url", "")

        ingredients = recipe.get("ingredients", [])
        steps = recipe.get("steps", [])
        servings = recipe.get("servings", 4)
        prep_time = recipe.get("prep_time", "20 minutes")

        ing_list = "\n".join([f"- [ ] {ing}" for ing in ingredients])
        steps_list = "\n".join([f"{idx+1}. {step}" for idx, step in enumerate(steps)])

        urls = _extract_urls(summary)
        resources_md = ""
        if urls:
            resources_md = "\n\n**External Resources Discovered:**\n" + "\n".join([f"- [Resource Link]({u})" for u in urls])

        obsidian_md = f"\n\n[Open in Obsidian]({obs_url})" if obs_url else ""

        return (
            f"### [[{title}]]\n\n"
            f"**Instagram Reel Citation:** [@{title}]({link})\n"
            f"**Category:** [[{cat_label}]] > [[{subcat}]] > [[{concept}]]\n"
            f"**Yield:** {servings} servings | **Prep Time:** {prep_time}\n\n"
            f"**Summary:** {summary}{resources_md}\n\n"
            f"#### Ingredients\n{ing_list}\n\n"
            f"#### Preparation Steps\n{steps_list}"
            f"{obsidian_md}"
        )

    # 2. Specialized product list response if user asks for tools/CLI/products
    if any(k in q_lower for k in ["tool", "cli", "terminal", "product", "top"]) and product_reels:
        r = product_reels[0]
        title = r.get("title", "")
        link = r.get("url") or r.get("link", "")
        subcat = r.get("subcategory", "")
        concept = r.get("concept", "")
        cat_label = r.get("category_label", "Shopping & Products")
        summary = r.get("summary", "")
        products = r.get("product_list", [])
        obs_url = r.get("obsidian_url", "")

        prod_list_md = "\n".join([f"{idx+1}. [[{p}]]" for idx, p in enumerate(products)])
        urls = _extract_urls(summary)
        resources_md = ""
        if urls:
            resources_md = "\n\n**External Resources & Repositories:**\n" + "\n".join([f"- [External Link]({u})" for u in urls])

        obsidian_md = f"\n\n[Open in Obsidian]({obs_url})" if obs_url else ""

        return (
            f"### [[{title}]]\n\n"
            f"**Instagram Reel Citation:** [@{title}]({link})\n"
            f"**Category:** [[{cat_label}]] > [[{subcat}]] > [[{concept}]]\n\n"
            f"**Summary:** {summary}{resources_md}\n\n"
            f"#### Featured Products & Tools:\n{prod_list_md}"
            f"{obsidian_md}"
        )

    # 3. Comprehensive multi-reel synthesis (e.g. data science interview, system design)
    sections = []
    for r in search_results[:3]:
        title = r.get("title", "")
        link = r.get("url") or r.get("link", "")
        subcat = r.get("subcategory", "")
        concept = r.get("concept", "")
        cat_label = r.get("category_label", "")
        summary = r.get("summary", "")
        obs_url = r.get("obsidian_url", "")

        urls = _extract_urls(summary)
        links_md = ""
        if urls:
            links_md = "\n  - **Discovered Resources:** " + ", ".join([f"[Resource Link]({u})" for u in urls])

        obs_link_md = f" | [Open in Obsidian]({obs_url})" if obs_url else ""

        sections.append(
            f"#### [[{concept}]] in [[{subcat}]]\n"
            f"- **Reel Citation:** [@{title}]({link}){obs_link_md}\n"
            f"- **Overview:** {summary}{links_md}"
        )

    response_body = "\n\n".join(sections)
    return (
        f"### Knowledge Synthesis: {query.strip()}\n\n"
        f"Based on your saved reels across [[Technology & Education]] and related domains:\n\n"
        f"{response_body}\n\n"
        f"Use the interactive knowledge graph on the left to trace connected concepts across subcategories."
    )


def run_reel_agent(query: str, data_source: Optional[str] = None) -> str:
    """Execute the LangGraph agent and return the markdown response text.

    Resolution order:
      1. REELMIND_OFFLINE=1 -> deterministic graph engine (tests / CI).
      2. No API key -> deterministic graph engine (intentional offline mode).
      3. Gemini via LangGraph, trying each id from _model_candidates() in turn. A
         failing id is logged to stderr and the next one is attempted; if every id
         fails, the reason is surfaced in the response instead of being swallowed,
         so a stale model id, an invalid key, or a quota error can never masquerade
         as a normal answer.
    """
    global _LAST_AGENT_ERROR

    if data_source:
        get_graph_engine(data_source)

    if _offline_mode_forced():
        _LAST_AGENT_ERROR = "offline mode forced via REELMIND_OFFLINE"
        return _dynamic_fallback_runner(query)

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        _LAST_AGENT_ERROR = "GEMINI_API_KEY / GOOGLE_API_KEY is not set"
        return _dynamic_fallback_runner(query)

    result = None
    failures: List[str] = []
    for model_name in _model_candidates():
        agent = create_agent(api_key, model_name)
        try:
            result = agent.invoke({"messages": [HumanMessage(content=query)]})
            break
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            failure = f"{model_name}: {type(exc).__name__}: {exc}"
            failures.append(failure)
            print(f"[ReelMind] {model_name} failed -> {type(exc).__name__}; trying next candidate", file=sys.stderr)

    if result is None:
        error = " | ".join(failures) or "no Gemini model candidates configured"
        _LAST_AGENT_ERROR = error
        short = " | ".join(f"{f.split(': ', 1)[0]}: {f.split(': ', 1)[1] if ': ' in f else ''}"[:160] for f in failures)
        return (
            "> ⚠️ **Degraded mode - the LLM call failed on every configured model, so this "
            "answer was assembled by the deterministic graph engine.**\n"
            f"> \n> `{short[:500]}`\n\n"
            f"{_dynamic_fallback_runner(query)}"
        )

    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            if isinstance(msg.content, str):
                _LAST_AGENT_ERROR = None
                return msg.content
            if isinstance(msg.content, list):
                parts = [
                    p.get("text", "") if isinstance(p, dict) else str(p)
                    for p in msg.content
                ]
                _LAST_AGENT_ERROR = None
                return "".join(parts)

    _LAST_AGENT_ERROR = "Gemini returned no assistant message"
    print(f"[ReelMind] {_LAST_AGENT_ERROR}", file=sys.stderr)
    return _dynamic_fallback_runner(query)
