from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NewsSearchCache


def get_cached_searches(session: Session, cache_keys: list[str]) -> dict[str, NewsSearchCache]:
    if not cache_keys:
        return {}
    rows = session.scalars(select(NewsSearchCache).where(NewsSearchCache.cache_key.in_(cache_keys)))
    return {row.cache_key: row for row in rows}


def save_search(
    session: Session, cache_key: str, article_ids: list[int], cost_dollars: float | None, fetched_at: datetime
) -> None:
    """Insert or overwrite. `fetched_at` is always written so a re-run search gets a new timestamp."""
    session.merge(
        NewsSearchCache(cache_key=cache_key, article_ids=article_ids, cost_dollars=cost_dollars, fetched_at=fetched_at)
    )
