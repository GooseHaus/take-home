"""Read side for movements. The REST endpoints and the chat tools both go through here (D8)."""

from datetime import date

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.enums import Direction, MovementSort
from app.models import Company, Explanation, Movement, MovementArticle, Price
from app.schemas.movement_filters import MovementFilters

SORT_ORDER = {
    MovementSort.DATE_DESC: (Movement.date.desc(),),
    MovementSort.DATE_ASC: (Movement.date.asc(),),
    MovementSort.MAGNITUDE: (func.abs(Movement.pct_change).desc(), Movement.date.desc()),
}


def _apply_filters(stmt: Select, filters: MovementFilters) -> Select:
    needs_explanation = filters.explained_only or filters.category or filters.min_confidence is not None
    if needs_explanation:
        stmt = stmt.join(Explanation, Explanation.movement_id == Movement.id)
    if filters.start:
        stmt = stmt.where(Movement.date >= filters.start)
    if filters.end:
        stmt = stmt.where(Movement.date <= filters.end)
    if filters.direction is Direction.UP:
        stmt = stmt.where(Movement.pct_change > 0)
    if filters.direction is Direction.DOWN:
        stmt = stmt.where(Movement.pct_change < 0)
    if filters.min_abs_change is not None:
        stmt = stmt.where(func.abs(Movement.pct_change) >= filters.min_abs_change)
    if filters.driver_hint:
        stmt = stmt.where(Movement.driver_hint == filters.driver_hint)
    if filters.category:
        stmt = stmt.where(Explanation.category == filters.category)
    if filters.min_confidence is not None:
        stmt = stmt.where(Explanation.confidence >= filters.min_confidence)
    return stmt


def query_movements(session: Session, ticker: str, filters: MovementFilters) -> tuple[list[Movement], int]:
    """One page of movements (explanation + articles eagerly loaded) and the total matching the filters."""
    base = _apply_filters(select(Movement).where(Movement.ticker == ticker), filters)
    total = session.scalar(select(func.count()).select_from(base.subquery()))
    page = (
        base.options(
            selectinload(Movement.explanation),
            selectinload(Movement.article_links).selectinload(MovementArticle.article),
        )
        .order_by(*SORT_ORDER[filters.sort])
        .limit(filters.limit)
        .offset(filters.offset)
    )
    return list(session.scalars(page)), total or 0


def get_movement(session: Session, ticker: str, day: date) -> Movement | None:
    return session.scalars(select(Movement).where(Movement.ticker == ticker, Movement.date == day)).first()


def get_prices(session: Session, ticker: str, start: date | None, end: date | None) -> list[Price]:
    stmt = select(Price).where(Price.ticker == ticker)
    if start:
        stmt = stmt.where(Price.date >= start)
    if end:
        stmt = stmt.where(Price.date <= end)
    return list(session.scalars(stmt.order_by(Price.date)))


def price_date_range(session: Session, ticker: str) -> tuple[date | None, date | None]:
    return session.execute(select(func.min(Price.date), func.max(Price.date)).where(Price.ticker == ticker)).one()


def movement_counts(session: Session, ticker: str) -> tuple[int, int]:
    """(movements, movements with an explanation)."""
    total, explained = session.execute(
        select(func.count(Movement.id), func.count(Explanation.movement_id))
        .outerjoin(Explanation, Explanation.movement_id == Movement.id)
        .where(Movement.ticker == ticker)
    ).one()
    return total, explained


def list_companies(session: Session) -> list[Company]:
    return list(session.scalars(select(Company).order_by(Company.ticker)))
