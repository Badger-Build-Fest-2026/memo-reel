"""
Final structured-knowledge output.

Two layers:
  - envelope: always present, same shape for every reel
  - category payload: exactly ONE of recipe / product_list / concepts
    is populated, chosen by the reel's category. The other two stay
    None. This keeps the JSON clean per-category instead of one giant
    model with a pile of always-null fields.

Every evidence claim still carries a timestamp + frame_path back to
the Content Bundle - that provenance guarantee doesn't change.

GeneratedKnowledge vs ReelKnowledge: Gemini fills GeneratedKnowledge
(everything except the Instagram metadata, which it has no business
inventing). We then stitch reel_url/caption/saved_at in from the
Content Bundle afterward to build the final ReelKnowledge. Passing
GeneratedKnowledge as the API's response_schema makes Gemini's output
STRUCTURALLY conform to this shape (server-side), not just prompted
to - e.g. "concepts" is guaranteed to come back as ConceptItem
objects, never a bare string or some other shape the model invents.
"""

from typing import Literal

from pydantic import BaseModel

Category = Literal[
    "Food & Cooking",
    "Technology & Education",
    "Shopping & Products",
    "Fitness & Health",
    "Lifestyle & Travel",
    "Entertainment",
    "Other",
]


class EvidenceItem(BaseModel):
    claim: str
    timestamp: float
    frame_path: str


class LinkItem(BaseModel):
    url: str
    description: str


# ---- category-specific payloads ----

class RecipeDetails(BaseModel):
    ingredients: list[str]
    steps: list[str]
    servings: str | None = None
    cook_time: str | None = None


class ProductItem(BaseModel):
    name: str
    description: str
    price: str | None = None
    purchase_link: str | None = None


class ConceptItem(BaseModel):
    """
    A named concept/tool/idea with a short description - richer than
    a bare string so tool roundups ("Cap", "Keila", ...) can carry
    what each one actually is, not just a name.
    """
    name: str
    description: str


class ConceptDetails(BaseModel):
    concepts: list[ConceptItem]


# ---- envelope ----

class GeneratedKnowledge(BaseModel):
    """What Gemini actually fills in - no Instagram metadata fields."""
    title: str
    slug: str   # short, filename-friendly, e.g. "roundup_opensource" - see prompt for rules
    category: Category
    subcategory: str
    summary: str
    links: list[LinkItem] = []
    evidence: list[EvidenceItem]

    # exactly one of these should be non-null, matching `category`
    recipe: RecipeDetails | None = None
    product_list: list[ProductItem] | None = None
    concepts: ConceptDetails | None = None


class ReelKnowledge(GeneratedKnowledge):
    """Final output: GeneratedKnowledge + Instagram metadata stitched in."""
    reel_url: str | None = None
    caption: str | None = None
    saved_at: str | None = None
    transcript: str | None = None
    obsidian_url: str | None = None  # filled in later, once the Obsidian note is created