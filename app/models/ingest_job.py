from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import utcnow


class IngestJob(Base):
    __tablename__ = "ingest_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | running | done | failed
    stage: Mapped[str | None] = mapped_column(String(32))
    detail: Mapped[dict | None] = mapped_column(JSON)  # counts, cost, per-movement errors
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
