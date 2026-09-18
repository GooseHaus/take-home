from datetime import date

import pytest

from app.constants.market import MARKET_TICKER
from app.db import SessionLocal
from app.domain import Profile
from app.enums import ExplanationCategory, IngestStage, JobStatus, NewsTier
from app.errors import ProviderError
from app.models import Article, Explanation, IngestJob, Movement, MovementArticle, NewsSearchCache
from app.repositories.ingest_jobs import create_job, get_active_job, get_latest_job
from app.schemas.llm import ArticleRelevance, ExplanationOutput
from app.services.pipeline import run_ingest
from tests.factories import article_hit, price_frame
from tests.fakes.fake_llm_client import FakeLLMClient
from tests.fakes.fake_market_data_provider import FakeMarketDataProvider
from tests.fakes.fake_news_provider import FakeNewsProvider

START, END = date(2026, 1, 5), date(2026, 3, 31)
# Three moves over 2%: +5.0%, -4.0%, +3.0% (largest first by absolute size: day 2, day 4, day 6)
CLOSES = [100, 105, 105, 100.8, 100.8, 103.824, 103.824]


def market_data() -> FakeMarketDataProvider:
    frames = {"ACME": price_frame(CLOSES), MARKET_TICKER: price_frame([400] * len(CLOSES))}
    return FakeMarketDataProvider(frames, {"ACME": Profile("ACME", "Acme Corp", None, "Widgets", None)})


def explain_everything(user_prompt, response_model):
    ids = [int(chunk.split("]")[0]) for chunk in user_prompt.split("[id=")[1:]]
    return ExplanationOutput(
        summary="Acme moved on company news.",
        category=ExplanationCategory.COMPANY,
        confidence=0.8,
        article_relevance=[ArticleRelevance(article_id=i, relevance=0.9) for i in ids],
    )


def ingest(session, news, llm, limit=25, data=None) -> IngestJob:
    job = create_job(session, "ACME", {})
    session.commit()
    run_ingest(SessionLocal, job.id, "ACME", START, END, 2.0, limit, data or market_data(), news, llm)
    session.expire_all()
    return session.get(IngestJob, job.id)


def test_full_run_explains_every_movement_with_cited_articles(session):
    news, llm = FakeNewsProvider([article_hit("acme-a"), article_hit("acme-b")]), FakeLLMClient(explain_everything)
    job = ingest(session, news, llm)

    assert (job.status, job.stage, job.error) == (JobStatus.DONE, IngestStage.COMPLETE, None)
    assert job.detail["movements"] == 3 and job.detail["explained"] == 3 and job.detail["errors"] == []
    assert job.detail["news"]["searches_run"] == 3 and job.detail["news"]["cost_dollars"] == pytest.approx(0.021)
    assert session.query(Movement).count() == 3 and session.query(Explanation).count() == 3
    assert session.query(Article).count() == 2  # same articles found for every window, stored once
    links = session.query(MovementArticle).all()
    assert (
        len(links) == 6 and {ln.tier for ln in links} == {NewsTier.COMPANY} and {ln.relevance for ln in links} == {0.9}
    )
    assert all(query == "Acme Corp (ACME) stock news" for query, *_ in news.calls)


def test_rerun_makes_no_paid_calls(session):
    news, llm = FakeNewsProvider([article_hit("acme-a")]), FakeLLMClient(explain_everything)
    ingest(session, news, llm)
    calls_after_first = (len(news.calls), len(llm.calls))

    job = ingest(session, news, llm)
    assert (len(news.calls), len(llm.calls)) == calls_after_first
    assert job.status is JobStatus.DONE and job.detail["selected"] == 0 and job.detail["explained"] == 0
    assert session.query(Movement).count() == 3 and session.query(NewsSearchCache).count() == 3


def test_cost_guard_limits_paid_work_to_the_largest_moves(session):
    news, llm = FakeNewsProvider([article_hit("acme-a")]), FakeLLMClient(explain_everything)
    ingest(session, news, llm, limit=2)
    explained = {m.pct_change for m in session.query(Movement) if m.explanation}
    assert explained == {5.0, -4.0} and len(news.calls) == 2


def test_one_failed_explanation_does_not_fail_the_job_and_is_retried_next_time(session):
    calls = {"n": 0}

    def flaky(user_prompt, response_model):
        calls["n"] += 1
        if "2026-01-06" in user_prompt and calls["n"] <= 3:
            raise ProviderError("rate limited")
        return explain_everything(user_prompt, response_model)

    news = FakeNewsProvider([article_hit("acme-a")])
    job = ingest(session, news, FakeLLMClient(flaky))
    assert job.status is JobStatus.DONE and job.detail["explained"] == 2
    assert job.detail["errors"] == ["2026-01-06: rate limited"]

    retry = ingest(session, news, FakeLLMClient(flaky))
    assert retry.detail["explained"] == 1 and len(news.calls) == 3  # news came from the cache
    assert session.query(Explanation).count() == 3


def test_failed_news_search_still_lets_the_movement_be_explained(session):
    class BrokenNews(FakeNewsProvider):
        def search(self, query, start, end, limit):
            raise ProviderError("exa down")

    job = ingest(session, BrokenNews(), FakeLLMClient(explain_everything))
    assert job.status is JobStatus.DONE and len(job.detail["errors"]) == 3
    assert session.query(NewsSearchCache).count() == 0  # failures aren't cached, so the next ingest retries them


def test_unknown_ticker_fails_the_job_cleanly(session):
    job = ingest(session, FakeNewsProvider(), FakeLLMClient(explain_everything), data=FakeMarketDataProvider({}))
    assert job.status is JobStatus.FAILED and "No price data" in job.error
    assert job.finished_at is not None and session.query(Movement).count() == 0


def test_active_and_latest_job_lookups(session):
    first = create_job(session, "ACME", {"threshold": 2.0})
    session.commit()
    assert get_active_job(session, "ACME").id == first.id
    ingest(session, FakeNewsProvider(), FakeLLMClient(explain_everything))
    assert get_latest_job(session, "ACME").id > first.id
