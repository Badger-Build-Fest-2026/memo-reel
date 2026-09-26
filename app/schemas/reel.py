import re
from datetime import datetime
from enum import Enum
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, field_validator

_INSTAGRAM_REEL_URL = re.compile(
    r"https://www\.instagram\.com/reels?/([A-Za-z0-9_-]+)/?(?:\?.*)?"
)


class CaptureMode(str, Enum):
    selected_content = "selected_content"


class ReelSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str
    account_name: str
    source_url: str
    hashtags: str
    caption: str = ""
    requested_at: datetime

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.netloc != "www.instagram.com":
            raise ValueError(
                "source_url must be an HTTPS Instagram Reel URL, "
                "for example https://www.instagram.com/reel/<reel_id>/"
            )

        match = _INSTAGRAM_REEL_URL.fullmatch(value)
        if not match:
            raise ValueError(
                "source_url must be an Instagram Reel URL, "
                "for example https://www.instagram.com/reel/<reel_id>/"
            )
        return f"https://www.instagram.com/reel/{match.group(1)}/"

    @field_validator("caption")
    @classmethod
    def strip_caption(cls, value: str) -> str:
        return value.strip()


class ReelSubmissionResponse(BaseModel):
    status: str = "queued"
    capture_id: str
    job_status: str = "queued"
    source_url: str
    capture_mode: CaptureMode
    requested_at: datetime
