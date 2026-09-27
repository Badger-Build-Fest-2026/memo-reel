from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


CREATE_SUBMISSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS submissions (
	capture_id UUID PRIMARY KEY,
	user_id VARCHAR(255) NOT NULL,
	account_name VARCHAR(255) NOT NULL,
	source_url VARCHAR(2048) NOT NULL,
	hashtags TEXT NOT NULL DEFAULT '',
	caption TEXT NOT NULL DEFAULT '',
	requested_at TIMESTAMPTZ NOT NULL,
	status VARCHAR(32) NOT NULL DEFAULT 'queued',
	job_status VARCHAR(32) NOT NULL DEFAULT 'queued',
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_submissions_source_url
	ON submissions (source_url);

CREATE UNIQUE INDEX IF NOT EXISTS uq_submissions_source_url
	ON submissions (source_url);
"""


class ReelSubmission(Base):
    __tablename__ = "submissions"
    __table_args__ = (Index("uq_submissions_source_url", "source_url", unique=True),)

    capture_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    hashtags: Mapped[str] = mapped_column(Text, nullable=False, default="")
    caption: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    job_status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
