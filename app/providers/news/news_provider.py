from datetime import date
from typing import Protocol

from app.domain import NewsSearchResult


class NewsProvider(Protocol):
    """Date-bounded news search."""

    def search(self, query: str, start: date, end: date, limit: int) -> NewsSearchResult:
        """Articles published within [start, end] (inclusive days) matching a natural-language query.

        Raises ProviderError when the upstream call fails.
        """
        ...
