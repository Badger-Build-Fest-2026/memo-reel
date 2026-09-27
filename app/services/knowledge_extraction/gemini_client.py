"""
Sends the Content Bundle (frames + timestamps + transcript) to
Gemini and asks for structured knowledge back.

Important: we send the curated FRAMES + TEXT, not the raw video
file. See project notes - raw video loses timestamp precision and
is more expensive at scale; the frame+transcript bundle keeps the
evidence/provenance story intact (each claim traces back to an
exact frame).

Requires a free Gemini API key from https://aistudio.google.com/apikey
set as the GEMINI_API_KEY environment variable.
"""

import json
from dotenv import load_dotenv
import os

load_dotenv()

from PIL import Image

from app.schemas.bundle import ContentBundle
from app.schemas.knowledge import StructuredKnowledge

DEFAULT_MODEL = "gemini-2.0-flash"

_SYSTEM_PROMPT = """You are analyzing a short-form educational video (an Instagram Reel).
You are given a sequence of representative frames from the video, each paired with a
timestamp and the transcript text spoken around that moment.

Convert this into structured, reusable knowledge. Return ONLY valid JSON matching this
exact shape, with no markdown fences or extra commentary:

{
  "topic": "short topic name",
  "concepts": ["concept1", "concept2", ...],
  "resources": ["any named tool/resource/link mentioned, if any"],
  "summary": "2-4 sentence summary of the video's content",
  "evidence": [
    {"claim": "a specific fact or concept shown/said", "timestamp": 12.5, "frame_path": "path/to/frame.jpg"}
  ]
}

Rules:
- Every item in "evidence" MUST use a timestamp and frame_path taken from the frames given to you.
- Ground every claim in something actually visible on screen or said in the transcript - do not invent facts.
- Prefer concrete, specific concepts over vague generalities.
"""


def _build_prompt_parts(bundle: ContentBundle) -> list:
    parts: list = [_SYSTEM_PROMPT, f"\nFull transcript:\n{bundle.full_transcript}\n\nFrames:"]
    for m in bundle.moments:
        parts.append(f"\n--- Frame at {m.timestamp}s (frame_path: {m.frame_path}) ---")
        parts.append(f"Spoken around this moment: \"{m.spoken_text}\"")
        parts.append(Image.open(m.frame_path))
    return parts


def extract_structured_knowledge(
    bundle: ContentBundle,
    api_key: str | None = None,
    model_name: str = DEFAULT_MODEL,
) -> StructuredKnowledge:
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
    response = client.models.generate_content(
        model=model_name,
        contents=parts,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    raw = response.text.strip()
    # Defensive: strip markdown fences if the model adds them despite instructions
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    data = json.loads(raw)
    return StructuredKnowledge(**data)