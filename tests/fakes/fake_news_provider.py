from datetime import date

from app.domain import ArticleHit, NewsSearchResult


class FakeNewsProvider:
    """NewsProvider returning canned hits and recording every call, so tests can assert on cache behaviour."""

    def __init__(self, hits: list[ArticleHit] | None = None, cost_dollars: float = 0.007):
        self.hits = hits or []
        self.cost_dollars = cost_dollars
        self.calls: list[tuple[str, date, date, int]] = []

    def search(self, query: str, start: date, end: date, limit: int) -> NewsSearchResult:
        self.calls.append((query, start, end, limit))
        return NewsSearchResult(hits=self.hits[:limit], cost_dollars=self.cost_dollars)
