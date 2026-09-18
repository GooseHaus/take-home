from collections.abc import Callable
from datetime import date

from app.domain import ArticleHit, NewsSearchResult


class FakeNewsProvider:
    """NewsProvider returning canned hits and recording every call, so tests can assert on cache behaviour.

    `responder(query)` overrides the fixed `hits` when results should depend on the query (i.e. on the tier).
    """

    def __init__(
        self,
        hits: list[ArticleHit] | None = None,
        cost_dollars: float = 0.007,
        responder: Callable[[str], list[ArticleHit]] | None = None,
    ):
        self.hits = hits or []
        self.cost_dollars = cost_dollars
        self.responder = responder
        self.calls: list[tuple[str, date, date, int]] = []

    def search(self, query: str, start: date, end: date, limit: int) -> NewsSearchResult:
        self.calls.append((query, start, end, limit))
        hits = self.responder(query) if self.responder else self.hits
        return NewsSearchResult(hits=hits[:limit], cost_dollars=self.cost_dollars)

    def queries(self) -> list[str]:
        return [query for query, *_ in self.calls]
