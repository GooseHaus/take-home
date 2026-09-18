import logging
import time
from datetime import date, datetime

from exa_py import Exa

from app.constants.news import EXA_CATEGORY, EXA_CONTENTS, EXA_SEARCH_TYPE, SNIPPET_MAX_CHARS, TITLE_MAX_CHARS
from app.domain import ArticleHit, NewsSearchResult
from app.errors import ProviderError, ProviderNotConfigured
from app.utils.text import clean_text
from app.utils.urls import normalize_url, source_domain

logger = logging.getLogger(__name__)


class ExaNewsProvider:
    def __init__(self, api_key: str):
        if not api_key:
            raise ProviderNotConfigured("EXA_API_KEY is not set")
        self._client = Exa(api_key)

    def search(self, query: str, start: date, end: date, limit: int) -> NewsSearchResult:
        started = time.perf_counter()
        try:
            response = self._client.search(
                query,
                type=EXA_SEARCH_TYPE,
                category=EXA_CATEGORY,
                num_results=limit,
                # Hard filters: undated or misdated pages are dropped (tradeoff noted in D5)
                start_published_date=f"{start.isoformat()}T00:00:00Z",
                end_published_date=f"{end.isoformat()}T23:59:59Z",
                contents=EXA_CONTENTS,
            )
            hits = [hit for result in response.results if (hit := self._to_hit(result))]
        except Exception as exc:
            raise ProviderError(f"Exa search failed: {exc}") from exc

        cost = getattr(getattr(response, "cost_dollars", None), "total", None)
        logger.info(
            "exa search %r %s..%s -> %d hits, $%s, %.2fs",
            query,
            start,
            end,
            len(hits),
            cost,
            time.perf_counter() - started,
        )
        return NewsSearchResult(hits=hits, cost_dollars=cost)

    @staticmethod
    def _to_hit(result) -> ArticleHit | None:
        if not result.url or not result.title:
            return None
        highlights = " ... ".join(result.highlights or [])
        return ArticleHit(
            url=normalize_url(result.url),
            title=clean_text(result.title, TITLE_MAX_CHARS),
            source=source_domain(result.url),
            published_at=_parse_datetime(result.published_date),
            snippet=clean_text(highlights, SNIPPET_MAX_CHARS),
        )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
