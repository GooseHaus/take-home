from dataclasses import asdict
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain import DetectedMovement
from app.enums import NewsTier
from app.models import Article, Explanation, Movement, MovementArticle


def upsert_movements(session: Session, ticker: str, detected: list[DetectedMovement]) -> list[Movement]:
    """Insert new movements and refresh the stats of existing ones (prices get re-adjusted; ids and links survive)."""
    existing = {m.date: m for m in session.scalars(select(Movement).where(Movement.ticker == ticker))}
    movements = []
    for item in detected:
        movement = existing.get(item.date) or Movement(ticker=ticker, date=item.date)
        for column, value in asdict(item).items():
            setattr(movement, column, value)
        session.add(movement)
        movements.append(movement)
    session.flush()
    return movements


def link_articles(session: Session, movement: Movement, articles: list[Article], tier: NewsTier) -> int:
    """Attach articles to a movement. An article already linked (by an earlier tier) keeps its first tier."""
    linked = set(session.scalars(select(MovementArticle.article_id).where(MovementArticle.movement_id == movement.id)))
    new = [a for a in articles if a.id not in linked]
    session.add_all(MovementArticle(movement_id=movement.id, article_id=a.id, tier=tier) for a in new)
    session.flush()
    return len(new)


def linked_articles(session: Session, movement: Movement) -> list[tuple[MovementArticle, Article]]:
    rows = session.execute(
        select(MovementArticle, Article)
        .join(Article, Article.id == MovementArticle.article_id)
        .where(MovementArticle.movement_id == movement.id)
        .order_by(Article.published_at, Article.id)
    ).all()
    return [(link, article) for link, article in rows]


def delete_undetected_movements(session: Session, ticker: str, start: date, end: date, detected: set[date]) -> int:
    """Remove movements in [start, end] that the latest detection did not produce, e.g. after a higher threshold.

    Explained movements are kept: they were paid for, and the API can still filter them out with `min_abs_change`.
    """
    explained = select(Explanation.movement_id)
    stale = list(
        session.scalars(
            select(Movement.id).where(
                Movement.ticker == ticker,
                Movement.date >= start,
                Movement.date <= end,
                Movement.date.not_in(detected),
                Movement.id.not_in(explained),
            )
        )
    )
    if stale:
        session.execute(delete(MovementArticle).where(MovementArticle.movement_id.in_(stale)))
        session.execute(delete(Movement).where(Movement.id.in_(stale)))
    return len(stale)
