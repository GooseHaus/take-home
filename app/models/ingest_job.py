from datetime import datetime

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.enums import JobStatus
from app.models.base import enum_column, utcnow
from app.models.utc_datetime import UTCDateTime


class IngestJob(Base):
    __tablename__ = "ingest_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[JobStatus] = enum_column(JobStatus, default=JobStatus.PENDING)
    stage: Mapped[str | None] = mapped_column(String(32))
    detail: Mapped[dict | None] = mapped_column(JSON)  # counts, cost, per-movement errors
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
