import re

from pydantic import BaseModel, field_validator

_INSTAGRAM_REEL_URL = re.compile(
    r"https://www\.instagram\.com/reels/[A-Za-z0-9_-]+/?"
)


class ReelSubmissionRequest(BaseModel):
    user_id: str
    reel_url: str

    @field_validator("reel_url")
    @classmethod
    def validate_reel_url(cls, value: str) -> str:
        if not _INSTAGRAM_REEL_URL.fullmatch(value):
            raise ValueError(
                "reel_url must be an Instagram Reels URL, "
                "for example https://www.instagram.com/reels/<reel_id>/"
            )
        return value


class ReelSubmissionResponse(BaseModel):
    status: str = "received"
    user_id: str
    reel_url: str