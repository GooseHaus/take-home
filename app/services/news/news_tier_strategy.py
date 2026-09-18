from typing import Protocol

from app.enums import NewsTier
from app.models import Company, Movement


class NewsTierStrategy(Protocol):
    """One way of looking for news that could explain a movement. Register implementations in `registry.py`."""

    tier: NewsTier

    def build_query(self, movement: Movement, company: Company) -> str | None:
        """Natural-language search query, or None when this tier has nothing to search for."""
        ...

    def cache_scope(self, movement: Movement, company: Company) -> str:
        """What the results are specific to (a ticker, an industry, nothing). Same scope + window = same search."""
        ...
