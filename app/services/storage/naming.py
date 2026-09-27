import re

_MAX_TOTAL_LEN = 40
_MAX_FIELD_LEN = 7

CATEGORY_ABBR = {
    "Food & Cooking": "food",
    "Technology & Education": "teched",
    "Shopping & Products": "shop",
    "Fitness & Health": "fitness",
    "Lifestyle & Travel": "lifestyle",
    "Entertainment": "ent",
    "Other": "other",
}


def _slugify(text: str, max_len: int) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text[:max_len].rstrip("_") or "untitled"


def _category_slug(category: str) -> str:
    return CATEGORY_ABBR.get(category, _slugify(category, 10))


def make_filename(
    category: str,
    subcategory: str,
    title: str,
    ext: str = "json",
) -> str:

    cat_slug = _category_slug(category)
    sub_slug = _slugify(subcategory, _MAX_FIELD_LEN)
    title_slug = _slugify(title, _MAX_FIELD_LEN)

    return f"{cat_slug}_{sub_slug}_{title_slug}.{ext}"