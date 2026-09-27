"""
Sends the Content Bundle (frames + timestamps + transcript) to
Gemini and asks for structured, category-routed knowledge back.

Important: we send the curated FRAMES + TEXT, not the raw video
file. Raw video loses timestamp precision and is more expensive at
scale; the frame+transcript bundle keeps the evidence/provenance
story intact (each claim traces back to an exact frame).

This is a single call, not a classify-then-extract two-call
pipeline: the schema carries all category-specific fields as
optional, and the prompt tells the model to classify first, then
populate only the block matching that category. Simpler and
cheaper than two round-trips, and avoids the two calls disagreeing
with each other.

We pass GeneratedKnowledge as response_schema, which makes Gemini's
JSON output structurally conform to that Pydantic model server-side
- not just prompted to. This is what prevents cases like "concepts"
coming back as bare strings for one reel and rich objects for
another; the shape is enforced, not hoped for.

Amazon link lookup for Shopping & Products is a SEPARATE second
call using Google Search grounding, not folded into the main call.
Combining strict JSON-schema output with search-grounding tools in
one call isn't reliably supported, so this stays a two-step process:
(1) structured extraction as before, (2) if it's a shopping reel
with products, a follow-up search-grounded call to find real
purchase links, merged back in afterward. If step 2 fails for any
reason, we fail soft - the rest of the result still returns fine,
just without purchase links.

Requires a free Gemini API key from https://aistudio.google.com/apikey
set as the GEMINI_API_KEY environment variable.
"""

import json
import os

from PIL import Image

from app.schemas.bundle import ContentBundle
from app.schemas.knowledge import GeneratedKnowledge, ProductItem, ReelKnowledge

DEFAULT_MODEL = "gemini-3.5-flash"

_SYSTEM_PROMPT = """You are analyzing a short-form video (an Instagram Reel). You are given
a sequence of representative frames, each paired with a timestamp and the transcript text
spoken around that moment, plus the reel's caption if available.

STEP 1 - Classify the reel into exactly one of these categories:
Food & Cooking | Technology & Education | Shopping & Products | Fitness & Health |
Lifestyle & Travel | Entertainment | Other
Also give a short, specific subcategory (e.g. "Recipe", "System Design", "Tool Roundup").

STEP 2 - Generate a "slug": 2-3 words max, lowercase, snake_case, capturing the core
subject concisely for use in a filename. Compress aggressively - drop filler words like
"tool", "the", "useful", "best", "top". Examples:
  "Useful Open-Source GitHub Repositories" (Tool Roundup) -> "roundup_opensource"
  "The Best High-Protein Sandwich You'll Ever Make" (Recipe) -> "protein_sandwich"
  "Top 10 Perfumes For Men in 2026" (Fragrance Roundup) -> "perfume_roundup"

STEP 3 - Based on the category, populate exactly ONE of these three fields and leave the
other two as null:
- "recipe": if Food & Cooking and it's a recipe/cooking demo.
- "product_list": if Shopping & Products (physical products, hauls, gear roundups).
- "concepts": if Technology & Education, or any content explaining ideas, tools, software,
  or techniques (including tool/app roundups like "4 screen recording tools").
If none of these three fit well (e.g. Entertainment, Lifestyle & Travel), leave all three null.

STEP 4 - Links: put EVERY link/URL/named resource actually shown on screen or mentioned in
the transcript/caption into the top-level "links" field as {"url": ..., "description": ...}.
This is the ONLY place links go - do not create any other links/resources list elsewhere.

Rules:
- Every "evidence" item MUST use a timestamp and frame_path taken from the frames given to you - never invent one.
- Ground every claim in something actually visible on screen or said in the transcript - do not invent facts.
- purchase_link and other URLs: only include if actually shown/mentioned in the reel. Do not fabricate a link. Leave it null rather than guessing.
- Prefer concrete, specific detail over vague generalities.
"""

_AMAZON_SEARCH_PROMPT = """For each of the following products, search for a real purchase
link - strongly prefer amazon.com if the product is available there, otherwise the most
relevant official/retail page. Use your search tool; do not guess or invent a URL.

Products:
{product_list}

Return ONLY a JSON array, no markdown fences, no commentary, in this exact shape:
[{{"name": "<product name, exactly as given above>", "purchase_link": "<url or null if none found>"}}]
"""


def _build_prompt_parts(bundle: ContentBundle) -> list:
    header = _SYSTEM_PROMPT + f"\nCaption: {bundle.caption or '(none provided)'}\n"
    parts: list = [header, f"\nFull transcript:\n{bundle.full_transcript}\n\nFrames:"]
    for m in bundle.moments:
        parts.append(f"\n--- Frame at {m.timestamp}s (frame_path: {m.frame_path}) ---")
        parts.append(f"Spoken around this moment: \"{m.spoken_text}\"")
        parts.append(Image.open(m.frame_path))
    return parts


def _find_amazon_links(client, products: list[ProductItem], model_name: str) -> list[ProductItem]:
    """
    Best-effort: search for a real purchase link per product using Google
    Search grounding. Fails soft - if anything goes wrong, returns the
    products unchanged rather than breaking the whole pipeline over a
    link lookup.
    """
    from google.genai import types

    try:
        product_names = "\n".join(f"- {p.name}: {p.description}" for p in products)
        prompt = _AMAZON_SEARCH_PROMPT.format(product_list=product_names)

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        link_results = {item["name"]: item.get("purchase_link") for item in json.loads(raw)}

        for product in products:
            found_link = link_results.get(product.name)
            if found_link:
                product.purchase_link = found_link

    except Exception:
        # Link lookup is a nice-to-have, not a hard dependency - if search
        # grounding fails/errors/returns junk, just skip it silently and
        # keep whatever purchase_links (likely None) were already there.
        pass

    return products


def extract_structured_knowledge(
    bundle: ContentBundle,
    api_key: str | None = None,
    model_name: str = DEFAULT_MODEL,
) -> ReelKnowledge:
    from google import genai
    from google.genai import types

    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "No Gemini API key found. Set the GEMINI_API_KEY env var "
            "(get a free one at https://aistudio.google.com/apikey)."
        )

    client = genai.Client(api_key=api_key)

    parts = _build_prompt_parts(bundle)
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeneratedKnowledge,
            ),
        )
    except Exception as error:
        print("Gemini API call failed:", str(error))
        raise RuntimeError("Gemini knowledge extraction failed") from error

    # response.parsed is already a validated GeneratedKnowledge instance
    # when response_schema is a Pydantic model - no manual json.loads needed.
    generated: GeneratedKnowledge = response.parsed

    if generated.category == "Shopping & Products" and generated.product_list:
        generated.product_list = _find_amazon_links(client, generated.product_list, model_name)

    return ReelKnowledge(
        **generated.model_dump(),
        reel_url=bundle.reel_url,
        caption=bundle.caption,
        saved_at=bundle.saved_at,
        transcript=bundle.full_transcript,
    )