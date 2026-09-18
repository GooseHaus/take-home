from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import DetectedMovement
from app.enums import NewsTier
from app.models import Article, Movement, MovementArticle


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
