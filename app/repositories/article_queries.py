from datetime import date, datetime, time

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.enums import NewsTier
from app.models import Article, Movement, MovementArticle


def search_articles(
    session: Session,
    query: str,
    ticker: str | None,
    start: date | None,
    end: date | None,
    tier: NewsTier | None,
    limit: int,
) -> list[tuple[Article, list[Movement]]]:
    """Case-insensitive substring match on title/snippet (D8: FTS5 is the upgrade path). Most relevant links first."""
    pattern = f"%{query.strip()}%"
    stmt = (
        select(Article, Movement)
        .join(MovementArticle, MovementArticle.article_id == Article.id)
        .join(Movement, Movement.id == MovementArticle.movement_id)
        .where(or_(Article.title.ilike(pattern), Article.snippet.ilike(pattern)))
    )
    if ticker:
        stmt = stmt.where(Movement.ticker == ticker)
    if tier:
        stmt = stmt.where(MovementArticle.tier == tier)
    if start:
        stmt = stmt.where(Article.published_at >= datetime.combine(start, time.min))
    if end:
        stmt = stmt.where(Article.published_at <= datetime.combine(end, time.max))
    stmt = stmt.order_by(MovementArticle.relevance.desc().nulls_last(), Article.published_at.desc())

    grouped: dict[int, tuple[Article, list[Movement]]] = {}
    for article, movement in session.execute(stmt):
        if article.id not in grouped and len(grouped) >= limit:
            continue
        grouped.setdefault(article.id, (article, []))[1].append(movement)
    return list(grouped.values())
