"""
This is the final product output — what RecallGraph actually shows
the user. Every claim carries a timestamp + frame_path back to the
Content Bundle, which is the "evidence and provenance" your spec
calls out as the actual differentiator (section 1/12).
"""

from pydantic import BaseModel


class EvidenceItem(BaseModel):
    claim: str            # a specific fact/concept extracted from the content
    timestamp: float       # where in the video this was shown/said
    frame_path: str        # the frame that proves it


class StructuredKnowledge(BaseModel):
    topic: str
    concepts: list[str]
    resources: list[str] = []
    summary: str
    evidence: list[EvidenceItem]