"""When cached news can be trusted and which moves are recent. Pure functions (D19)."""

from datetime import date, timedelta

from app.constants.pipeline import NEWS_SETTLE_DAYS, RECENT_MOVE_DAYS


def is_settled(window_end: date, fetched_on: date) -> bool:
    """True when the search ran late enough after its window closed that later coverage was already published."""
    return fetched_on >= window_end + timedelta(days=NEWS_SETTLE_DAYS)


def is_recent(move_date: date, today: date) -> bool:
    return move_date >= today - timedelta(days=RECENT_MOVE_DAYS)
