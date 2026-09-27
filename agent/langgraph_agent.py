"""LangGraph Agent Engine for Instagram Reels Multimodal Knowledge Graph.

Finalized Lakebase Schema:
Category -> Subcategory -> Concept -> Reel
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional
import warnings
from agent.graph_engine import ReelGraphEngine
from agent.mcb_web_fetcher import enrich_from_web
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
# In agent/langgraph_agent.py:
from agent.tools import ReelAgentTools

warnings.filterwarnings(
    "ignore", category=UserWarning, module="langchain_google_genai"
)

load_dotenv()

_LAKEBASE_URL = os.getenv("LAKEBASE_DATABASE_URL")
_DEFAULT_DATA_SOURCE = (
    _LAKEBASE_URL if _LAKEBASE_URL else "data/dummy_reels.jsonl"
)
_engine_instance: Optional[ReelGraphEngine] = None
_LAST_AGENT_ERROR: Optional[str] = None
_RESOLVED_WORKING_MODEL: Optional[str] = None

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
FALLBACK_GEMINI_MODEL = "gemini-2.5-flash-lite"


def find_working_gemini_model(api_key: str) -> Optional[str]:
  global _RESOLVED_WORKING_MODEL
  if _RESOLVED_WORKING_MODEL:
    return _RESOLVED_WORKING_MODEL

  candidates = [
      os.getenv("GEMINI_MODEL"),
      "gemini-3.5-flash-lite",
      "gemini-2.5-flash-lite",
      "gemini-flash-lite-latest",
      "gemini-2.5-flash",
      "gemini-3.8-flash",
  ]
  seen = set()
  ordered_candidates = [
      m for m in candidates if m and not (m in seen or seen.add(m))
  ]

  print(
      "[ReelMind] Probing available Gemini models for active quota...",
      file=sys.stderr,
  )
  for candidate in ordered_candidates:
    try:
      test_llm = ChatGoogleGenerativeAI(
          model=candidate,
          google_api_key=api_key,
          temperature=0.0,
          max_retries=0,
      )
      test_llm.invoke([HumanMessage(content="ping")])
      print(f"[ReelMind] Model selected and ready: {candidate}", file=sys.stderr)
      _RESOLVED_WORKING_MODEL = candidate
      return candidate
    except Exception as exc:
      err_msg = str(exc)
      if (
          "ResourceExhausted" in err_msg
          or "429" in err_msg
          or "RateLimit" in err_msg
      ):
        reason = "Quota / Rate Limit Exceeded"
      elif "404" in err_msg or "NotFound" in err_msg:
        reason = "Model endpoint not found"
      else:
        reason = type(exc).__name__
      print(f"  [-] {candidate}: {reason}", file=sys.stderr)

  return None


def get_graph_engine(data_source: Optional[str] = None) -> ReelGraphEngine:
  global _engine_instance
  if _engine_instance is None or (
      data_source
      and data_source != getattr(_engine_instance, "_current_source", None)
  ):
    source = data_source or _DEFAULT_DATA_SOURCE
    _engine_instance = ReelGraphEngine(source)
    setattr(_engine_instance, "_current_source", source)
  return _engine_instance


def _offline_mode_forced() -> bool:
  return os.getenv("REELMIND_OFFLINE", "").strip().lower() in {
      "1",
      "true",
      "yes",
  }


def get_last_agent_error() -> Optional[str]:
  return _LAST_AGENT_ERROR


SYSTEM_PROMPT = """You are RecallGraph, an expert multimodal knowledge retrieval assistant specialized in Instagram Reels knowledge graphs.

Follow these strict guidelines when formulating answers:
1. Ground every factual assertion directly in data retrieved from your tools.
2. Sourced citations MUST cite the Instagram Reel URL using this exact markdown link format:
   [@title or author](link)  (where link is the Instagram reel URL, e.g. https://www.instagram.com/reel/...)
3. LINK ENRICHMENT & RESOURCE SUMMARY:
   - When a retrieved reel contains items in its `links` list, review their URLs.
   - For technical questions, tool comparisons, or specific feature lookups, ALWAYS call `enrich_reel_links` or `fetch_external_url_context` on the links.
   - Summarize the key features and takeaways discovered from visiting those external pages directly in your final response under a dedicated "**Enriched Insights from Resources**" section.
4. Format every key category, subcategory, and concept in Obsidian wikilinks: [[Category]], [[Subcategory]], and [[Concept]].
5. Format ingredient lists with checklist checkboxes (- [ ] item) and steps with numbered lists.
6. STRICT SUBCATEGORY ISOLATION: Answer strictly within the domain of the user's inquiry.
"""

STOPWORDS = {
    "prep",
    "me",
    "for",
    "a",
    "an",
    "the",
    "in",
    "on",
    "of",
    "and",
    "or",
    "based",
    "my",
    "reels",
    "what",
    "show",
    "did",
    "i",
    "save",
    "saved",
}

SUBCATEGORY_ALIASES = {
    "data science": "Data Science",
    "machine learning": "Data Science",
    "mlops": "Data Science",
    "feature store": "Data Science",
    "feature pipelines": "Data Science",
    "model evaluation": "Data Science",
    "cross-validation": "Data Science",
    "system design": "System Design",
    "distributed systems": "System Design",
    "kafka": "System Design",
    "vector search": "System Design",
    "pgvector": "System Design",
    "high protein meals": "High Protein Meals",
    "meal prep": "High Protein Meals",
    "recipe": "High Protein Meals",
    "hypertrophy": "Hypertrophy",
    "productivity": "Productivity",
    "developer tools": "Productivity",
    "cli": "Productivity",
    "web design": "Tool Roundup",
    "tool roundup": "Tool Roundup",
    "live performance": "Live Performance",
    "student humor": "Student Humor",
}

SUBCATEGORY_SYNONYMS = {
    "Data Science": [
        "data science",
        "cross-validation",
        "out-of-time splits",
        "model evaluation",
        "scikit-learn",
    ],
    "System Design": [
        "system design",
        "distributed systems",
        "kafka",
        "vector search",
        "pgvector",
    ],
    "High Protein Meals": [
        "meal prep",
        "garlic chicken",
        "chicken",
        "spinach",
        "recipe",
    ],
    "Productivity": ["productivity", "cli", "terminal", "developer tools"],
    "Tool Roundup": ["web design", "originkit", "pryzm", "codepen", "ditther"],
}


def _resolve_subcategory(query: str) -> Optional[str]:
  q_lower = query.lower()
  for alias in sorted(SUBCATEGORY_ALIASES, key=len, reverse=True):
    if alias in q_lower:
      return SUBCATEGORY_ALIASES[alias]
  return None


@tool
def search_reels(query: str) -> List[Dict[str, Any]]:
  """Search for relevant reels across title, summary, transcription, category, and concepts."""
  engine = get_graph_engine()
  q_lower = query.lower()

  raw_tokens = set(re.findall(r"\w+", q_lower))
  informative_tokens = {
      t for t in raw_tokens if t not in STOPWORDS and len(t) > 2
  }

  resolved_subcategory = _resolve_subcategory(query)
  if resolved_subcategory:
    scoped_nodes = engine.get_reels_by_subcategory(resolved_subcategory)
    allowed_ids = {
        (node.get("capture_id") or node.get("link") or node.get("url"))
        for node in scoped_nodes
    }
    candidate_reels = [
        reel
        for reel in engine.reels.values()
        if (reel.get("capture_id") or reel.get("link") or reel.get("url"))
        in allowed_ids
    ]
    expanded_terms = set(informative_tokens) | set(
        SUBCATEGORY_SYNONYMS.get(resolved_subcategory, [])
    )
  else:
    candidate_reels = list(engine.reels.values())
    expanded_terms = set(informative_tokens)

  unique_candidates = []
  seen_ids = set()
  for reel in candidate_reels:
    uid = reel.get("capture_id") or reel.get("link") or reel.get("url")
    if uid in seen_ids:
      continue
    seen_ids.add(uid)
    unique_candidates.append(reel)

  scored_reels = []
  for reel in unique_candidates:
    title = reel.get("title", "")
    summary = reel.get("summary", "")
    transcription = reel.get("transcription", "")
    subcategory = reel.get("subcategory", "")
    concept = reel.get("concept", "")
    category = reel.get("category", "")
    cat_label = reel.get("category_label", "")

    text_corpus = (
        f"{title} {concept} {subcategory} {summary} {transcription} {category}"
        f" {cat_label}".lower()
    )
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
      elif t_lower in text_corpus:
        score += 1

    if score > 0:
      scored_reels.append((score, reel))

  scored_reels.sort(key=lambda x: x[0], reverse=True)
  if not scored_reels:
    scored_reels = [(0, r) for r in unique_candidates]

  results = []
  for _, r in scored_reels[:5]:
    results.append({
        "capture_id": r.get("capture_id"),
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
        "resource_urls": engine.get_reel_resources(
            r.get("capture_id") or r.get("link")
        ),
    })
  return results


@tool
def get_connected_topics(subcategory_or_category: str) -> List[str]:
  """Return topics related to a subcategory or category walking strictly downward."""
  engine = get_graph_engine()
  return engine.get_related_topics(subcategory_or_category)


@tool
def get_reel_details(reel_title_or_id: str) -> Dict[str, Any]:
  """Fetch complete reel details including clean resource URLs, recipe, and concepts."""
  engine = get_graph_engine()
  reel = engine.get_reel(reel_title_or_id)
  if not reel:
    return {"error": f"Reel '{reel_title_or_id}' not found."}

  cid = reel.get("capture_id") or reel.get("link")
  return {
      "capture_id": cid,
      "title": reel.get("title"),
      "url": reel.get("link"),
      "link": reel.get("link"),
      "category": reel.get("category"),
      "category_label": reel.get("category_label"),
      "subcategory": reel.get("subcategory"),
      "concept": reel.get("concept"),
      "concepts": reel.get("concepts", []),
      "summary": reel.get("summary"),
      "resource_urls": engine.get_reel_resources(cid),
      "recipe": reel.get("recipe"),
      "product_list": reel.get("product_list"),
      "evidence": reel.get("evidence", []),
      "obsidian_url": reel.get("obsidian_url"),
  }


@tool
def explore_topic_hierarchy(query_term: str) -> Dict[str, Any]:
  """Examine if a topic exists in the hierarchy and return all descendant leaf reels."""
  engine = get_graph_engine()
  node = engine.find_node(query_term)
  if not node:
    return {
        "found": False,
        "message": f"No node matches '{query_term}'.",
    }

  node_id = node["node_id"]
  reels = engine.get_subtree_reels(node_id)
  return {
      "found": True,
      "matched_node": node.get("name"),
      "tier": node.get("node_type"),
      "leaf_reels_count": len(reels),
      "reels": reels[:6],
  }

@tool
def enrich_reel_links(reel_title_or_id: str) -> Dict[str, Any]:
  """Visits all external URLs in a reel's 'links' array via MCP and returns extracted body content summaries."""
  engine = get_graph_engine()
  tools_instance = ReelAgentTools(engine, mcp_fetcher=enrich_from_web)
  return tools_instance.enrich_links(reel_title_or_id)

@tool
def fetch_external_url_context(url: str) -> str:
  """Fetch live clean markdown from a specific URL using FastMCP."""
  print(
      f"\n[TOOL CALL] enrich_from_web triggered for URL: {url}\n",
      file=sys.stderr,
  )
  return enrich_from_web(url)


ALL_TOOLS = [
    search_reels,
    get_connected_topics,
    get_reel_details,
    explore_topic_hierarchy,
    fetch_external_url_context,
]


def _model_candidates() -> List[str]:
  api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
  probed_model = find_working_gemini_model(api_key) if api_key else None
  raw_candidates = [
      probed_model,
      os.getenv("GEMINI_MODEL"),
      DEFAULT_GEMINI_MODEL,
      FALLBACK_GEMINI_MODEL,
      "gemini-flash-lite-latest",
  ]
  ordered = []
  for model in raw_candidates:
    if model and model not in ordered:
      ordered.append(model)
  return ordered


def create_agent(
    google_api_key: Optional[str] = None, model_name: Optional[str] = None
):
  api_key = (
      google_api_key
      or os.getenv("GEMINI_API_KEY")
      or os.getenv("GOOGLE_API_KEY")
  )
  if not api_key:
    return None
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
  search_results = search_reels.invoke({"query": query})
  if not search_results:
    return (
        "No relevant reels found in the knowledge graph. Try exploring"
        " categories like [[Technology & Education]] or [[Food & Cooking]]."
    )

  sections = []
  for r in search_results[:3]:
    title = r.get("title", "")
    link = r.get("url") or r.get("link", "")
    subcat = r.get("subcategory", "")
    concept = r.get("concept", "")
    summary = r.get("summary", "")
    urls = r.get("resource_urls", [])

    links_md = ""
    if urls:
      links_md = "\n  - **Discovered Resources:** " + ", ".join(
          [f"[Link]({u})" for u in urls]
      )

    sections.append(
        f"#### [[{concept}]] in [[{subcat}]]\n- **Reel Citation:**"
        f" [@{title}]({link})\n- **Overview:** {summary}{links_md}"
    )

  response_body = "\n\n".join(sections)
  return (
      f"### Knowledge Synthesis: {query.strip()}\n\nBased on your saved"
      f" reels:\n\n{response_body}"
  )


def run_reel_agent(query: str, data_source: Optional[str] = None) -> str:
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
    except Exception as exc:  # noqa: BLE001
      failure = f"{model_name}: {type(exc).__name__}: {exc}"
      failures.append(failure)
      print(
          f"[ReelMind] {model_name} failed -> {type(exc).__name__}; trying next"
          " candidate",
          file=sys.stderr,
      )

  if result is None:
    error = " | ".join(failures) or "no Gemini model candidates configured"
    _LAST_AGENT_ERROR = error
    return f"> ⚠️ **Degraded mode - LLM calls failed:**\n\n{_dynamic_fallback_runner(query)}"

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
  return _dynamic_fallback_runner(query)