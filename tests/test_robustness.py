"""Regression tests for problems found in the pre-submission review."""

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.constants.api import MAX_LOOKBACK_DAYS
from app.db import Base, make_engine
from app.dependencies import get_llm_client, get_market_data_provider, get_news_provider
from app.domain import ChatTurn, ToolCall
from app.enums import DriverHint, JobStatus, NewsTier
from app.errors import ProviderError
from app.main import app
from app.models import ChatMessage, Company, Explanation, IngestJob, Movement
from app.providers.market_data import YFinanceMarketDataProvider
from app.repositories.article_queries import search_articles
from app.repositories.articles import upsert_articles
from app.repositories.ingest_jobs import create_job
from app.repositories.movements import link_articles
from app.schemas.chat import Citation
from app.services.chat.chat_service import citations_in
from app.services.explain import TIER_QUOTAS, prompt_articles
from app.services.news.industry_tier import IndustryTier
from app.services.pipeline import run_ingest
from tests.factories import article_hit
from tests.fakes.fake_llm_client import FakeLLMClient
from tests.fakes.fake_news_provider import FakeNewsProvider
from tests.pipeline_helpers import END, START, ingest, llm_reply, market_data
from tests.seed import UP_DAY, seed_ticker

# --- SQLite write lock (needs a real file: the in-memory test engine is one shared connection) ------------------------


@pytest.fixture
def file_sessions(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'app.db'}", busy_timeout_seconds=0.5)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


def test_no_write_lock_is_held_while_prices_are_fetched(file_sessions):
    """During every provider fetch, another connection must be able to write (as a chat request would)."""
    provider = market_data("ACME")
    real_fetch = provider.fetch_history

    def fetch_while_someone_else_writes(ticker, start, end):
        with file_sessions() as other:
            other.add(ChatMessage(conversation_id="c1", role="user", content={"content": f"during {ticker}"}))
            other.commit()  # raises "database is locked" if the pipeline holds the write lock
        return real_fetch(ticker, start, end)

    provider.fetch_history = fetch_while_someone_else_writes
    with file_sessions() as session:
        job = create_job(session, "ACME", {})
        session.commit()
    run_ingest(
        file_sessions, job.id, "ACME", START, END, 2.0, 25, provider, FakeNewsProvider(), FakeLLMClient(llm_reply)
    )

    with file_sessions() as session:
        finished = session.get(IngestJob, job.id)
        assert (finished.status, finished.error) == (JobStatus.DONE, None)
        assert session.query(ChatMessage).count() >= 2  # ACME and SPY fetches both allowed a write


def test_an_unexpected_crash_is_recorded_without_leaking_details_and_never_raises(session):
    class Exploding(FakeNewsProvider):
        def search(self, query, start, end, limit):
            raise RuntimeError("SELECT secret FROM table -- internal detail")

    job = ingest(session, Exploding(), FakeLLMClient(llm_reply))
    assert job.status is JobStatus.FAILED
    assert job.error == "Unexpected RuntimeError. See the server log."


# --- request bounds ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"end": (date.today() + timedelta(days=1)).isoformat()},
        {"start": (date.today() + timedelta(days=1)).isoformat()},
        {"start": (date.today() - timedelta(days=MAX_LOOKBACK_DAYS + 1)).isoformat()},
        {"start": "1990-01-01", "end": "2026-01-01"},
        {"max_movements": 51},
        {"threshold_pct": 0.1},
    ],
)
def test_ingest_requests_that_could_run_up_a_bill_are_rejected(body):
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient(llm_reply)
    app.dependency_overrides[get_news_provider] = lambda: FakeNewsProvider()
    app.dependency_overrides[get_market_data_provider] = lambda: market_data("ACME")
    with TestClient(app) as client:
        assert client.post("/tickers/ACME/ingest", json=body).status_code == 422


def test_misspelt_filters_are_rejected_instead_of_ignored(session):
    seed_ticker(session)
    with TestClient(app) as client:
        assert client.get("/tickers/ACME?min_abs_chnage=4").status_code == 422
        assert client.get("/tickers/ACME?min_abs_change=4").status_code == 200


# --- timestamps -------------------------------------------------------------------------------------------------------


def test_timestamps_read_back_from_sqlite_are_utc(session):
    create_job(session, "ACME", {})
    session.commit()
    session.expire_all()
    assert session.query(IngestJob).one().started_at.tzinfo is UTC

    with TestClient(app) as client:
        assert client.get("/tickers/ACME/status").json()["started_at"].endswith("Z")


def test_aware_datetimes_are_converted_to_utc_before_storage(session):
    plus_two = datetime(2026, 7, 30, 14, 0, tzinfo=UTC).astimezone(tz=datetime.now().astimezone().tzinfo)
    (article,) = upsert_articles(session, [article_hit("tz", published_at=plus_two)])
    session.commit()
    session.expire_all()
    assert article.published_at == datetime(2026, 7, 30, 14, 0, tzinfo=UTC)


# --- explanation prompt -----------------------------------------------------------------------------------------------


def test_when_articles_exceed_the_quota_the_newest_of_each_tier_are_kept(session):
    seed_ticker(session)
    movement = session.query(Movement).filter_by(ticker="ACME", date=UP_DAY).one()
    quota = TIER_QUOTAS[NewsTier.MACRO]
    hits = [
        article_hit(f"macro-{day:02d}", published_at=datetime(2026, 1, day, tzinfo=UTC)) for day in range(1, quota + 4)
    ]
    link_articles(session, movement, upsert_articles(session, hits), NewsTier.MACRO)

    shown = [a.url.rsplit("/", 1)[1] for tier, a in prompt_articles(session, movement) if tier == "macro"]
    assert shown == [f"macro-{day:02d}" for day in range(4, quota + 4)]  # oldest three dropped, order oldest-first
    assert sum(1 for tier, _ in prompt_articles(session, movement) if tier == "company") == 2  # other tiers untouched


# --- movements after a threshold change -------------------------------------------------------------------------------


def test_raising_the_threshold_removes_unexplained_moves_but_keeps_paid_explanations(session):
    news, llm = FakeNewsProvider([article_hit("acme-a")]), FakeLLMClient(llm_reply)
    ingest(session, news, llm, limit=1)  # +5% explained; -4% and +3% detected only
    assert {m.pct_change for m in session.query(Movement)} == {5.0, -4.0, 3.0}

    job = create_job(session, "ACME", {})
    session.commit()
    run_ingest(
        sessionmaker(bind=session.get_bind()), job.id, "ACME", START, END, 6.0, 1, market_data("ACME"), news, llm
    )
    session.expire_all()
    assert {m.pct_change for m in session.query(Movement)} == {5.0}  # explained, so kept even though below 6%
    assert session.query(Explanation).count() == 1


# --- chat -------------------------------------------------------------------------------------------------------------


def test_a_crashing_tool_is_reported_to_the_model_not_returned_as_a_500(session, monkeypatch):
    seed_ticker(session)
    monkeypatch.setattr(
        "app.services.chat.tools.list_tickers_tool.ticker_data.list_ticker_summaries",
        lambda _session: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    seen = {}

    def final(messages):
        seen["tool_result"] = json.loads(messages[-1]["content"])
        return ChatTurn(content="Sorry, that lookup failed.")

    turns = [ChatTurn(content=None, tool_calls=[ToolCall("1", "list_tickers", "{}")]), final]
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient(turns=turns)
    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "what do you have?"})
    assert response.status_code == 200 and seen["tool_result"] == {"error": "The tool failed unexpectedly."}


def test_a_url_is_only_cited_when_the_whole_url_appears():
    short = Citation(title="Short", url="https://x.example/a", source=None)
    long = Citation(title="Long", url="https://x.example/a-b", source=None)
    seen = {c.url: c for c in (short, long)}
    assert citations_in("See [this](https://x.example/a-b).", seen) == [long]
    assert citations_in("See https://x.example/a, and [that](https://x.example/a-b)", seen) == [short, long]


def test_article_search_treats_wildcards_as_text(session):
    seed_ticker(session)
    assert search_articles(session, "%", None, None, None, None, 10) == []
    assert search_articles(session, "fed_", None, None, None, None, 10) == []
    assert len(search_articles(session, "fed", None, None, None, None, 10)) == 1


# --- providers and caching --------------------------------------------------------------------------------------------


def test_yfinance_failures_become_provider_errors(monkeypatch):
    class Broken:
        def __init__(self, ticker):
            pass

        def history(self, **kwargs):
            raise ConnectionError("rate limited")

    monkeypatch.setattr("app.providers.market_data.yfinance_market_data_provider.yf.Ticker", Broken)
    with pytest.raises(ProviderError, match="rate limited"):
        YFinanceMarketDataProvider().fetch_history("AAPL", START, END)


def test_industry_cache_key_changes_when_the_peers_change():
    tier = IndustryTier()
    movement = Movement(id=1, ticker="ACME", driver_hint=DriverHint.SECTOR, window_start=START, window_end=START)
    before = Company(ticker="ACME", name="Acme", industry="Widgets", peers=None)
    after = Company(ticker="ACME", name="Acme", industry="Widgets", peers=[{"name": "Globex", "ticker": "GLBX"}])
    assert tier.cache_scope(movement, before) != tier.cache_scope(movement, after)
    assert tier.cache_scope(movement, after) == tier.cache_scope(movement, after)
    assert tier.cache_scope(movement, after).startswith("ACME:")
