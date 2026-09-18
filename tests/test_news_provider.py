from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.constants.news import EXA_CATEGORY, EXA_CONTENTS, EXA_SEARCH_TYPE, SNIPPET_MAX_CHARS
from app.errors import ProviderError, ProviderNotConfigured
from app.models import Article
from app.providers.news import ExaNewsProvider
from app.repositories.articles import upsert_articles
from app.utils.text import clean_text
from app.utils.urls import normalize_url, source_domain
from tests.factories import article_hit

START, END = date(2026, 7, 30), date(2026, 8, 1)


class StubExaClient:
    def __init__(self, results=None, error: Exception | None = None):
        self.results = results or []
        self.error = error
        self.kwargs = None

    def search(self, query, **kwargs):
        self.kwargs = {"query": query, **kwargs}
        if self.error:
            raise self.error
        return SimpleNamespace(results=self.results, cost_dollars=SimpleNamespace(total=0.007))


def exa_result(**overrides):
    defaults = {
        "url": "https://www.Reuters.com/business/apple-forecast/?utm_source=x#top",
        "title": "Apple disappoints\n with forecast",
        "published_date": "2026-07-30T00:00:00.000Z",
        "highlights": ["Skip to   main content\n\nApple shares fell.", "Guidance missed."],
    }
    return SimpleNamespace(**{**defaults, **overrides})


def provider_with(stub: StubExaClient) -> ExaNewsProvider:
    provider = ExaNewsProvider("test-key")
    provider._client = stub
    return provider


def test_missing_key_is_a_typed_error():
    with pytest.raises(ProviderNotConfigured):
        ExaNewsProvider("")


def test_request_follows_the_documented_call_shape():
    stub = StubExaClient()
    provider_with(stub).search("Apple (AAPL) news", START, END, limit=5)
    assert stub.kwargs == {
        "query": "Apple (AAPL) news",
        "type": EXA_SEARCH_TYPE,
        "category": EXA_CATEGORY,
        "num_results": 5,
        "start_published_date": "2026-07-30T00:00:00Z",
        "end_published_date": "2026-08-01T23:59:59Z",  # end day is inclusive
        "contents": EXA_CONTENTS,
    }


def test_results_are_normalised_into_article_hits():
    result = provider_with(StubExaClient([exa_result()])).search("q", START, END, 5)
    (hit,) = result.hits
    assert hit.url == "https://www.reuters.com/business/apple-forecast"
    assert hit.source == "reuters.com"
    assert hit.title == "Apple disappoints with forecast"
    assert hit.published_at == datetime(2026, 7, 30, tzinfo=UTC)
    assert hit.snippet == "Skip to main content Apple shares fell. ... Guidance missed."
    assert result.cost_dollars == 0.007


def test_unusable_results_are_dropped_and_bad_dates_tolerated():
    results = [exa_result(url=None), exa_result(title=""), exa_result(published_date="not-a-date", highlights=None)]
    (hit,) = provider_with(StubExaClient(results)).search("q", START, END, 5).hits
    assert hit.published_at is None and hit.snippet is None


def test_upstream_failure_becomes_provider_error():
    with pytest.raises(ProviderError, match="quota"):
        provider_with(StubExaClient(error=RuntimeError("quota exceeded"))).search("q", START, END, 5)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("https://Example.com/a/?utm_source=x&utm_medium=y", "https://example.com/a"),
        ("https://example.com/a?id=7&fbclid=abc#section", "https://example.com/a?id=7"),
        ("https://example.com/a", "https://example.com/a"),
    ],
)
def test_normalize_url(raw, expected):
    assert normalize_url(raw) == expected


def test_source_domain_strips_www():
    assert source_domain("https://www.cnbc.com/2026/07/30/x.html") == "cnbc.com"


def test_clean_text_caps_on_a_word_boundary():
    cleaned = clean_text("word " * 500, SNIPPET_MAX_CHARS)
    assert len(cleaned) <= SNIPPET_MAX_CHARS + 3 and cleaned.endswith("word...")
    assert clean_text("   \n ", 10) is None


def test_upsert_articles_dedupes_within_batch_and_against_db(session):
    first = upsert_articles(session, [article_hit("a"), article_hit("b"), article_hit("a")])
    assert [a.url.rsplit("/", 1)[1] for a in first] == ["a", "b"]
    session.commit()

    second = upsert_articles(session, [article_hit("b", title="Changed headline"), article_hit("c")])
    session.commit()
    assert session.query(Article).count() == 3
    assert second[0].id == first[1].id and second[0].title == "B"  # existing row untouched
    assert upsert_articles(session, []) == []
