from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import utcnow


class NewsSearchCache(Base):
    """One row per executed news search, so re-ingest and macro searches shared across tickers cost nothing."""

    __tablename__ = "news_search_cache"

    cache_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    article_ids: Mapped[list] = mapped_column(JSON)
    cost_dollars: Mapped[float | None] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
