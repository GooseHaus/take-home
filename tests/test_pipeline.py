from datetime import date

import pytest

from app.constants.market import MARKET_TICKER
from app.constants.news import MACRO_QUERY
from app.db import SessionLocal
from app.domain import Profile
from app.enums import ExplanationCategory, IngestStage, JobStatus, NewsTier
from app.errors import ProviderError
from app.models import Article, Company, Explanation, IngestJob, Movement, MovementArticle, NewsSearchCache
from app.repositories.ingest_jobs import create_job, get_active_job, get_latest_job
from app.schemas.llm import ArticleRelevance, ExplanationOutput, PeersOutput
from app.services.pipeline import run_ingest
from tests.factories import article_hit, price_frame
from tests.fakes.fake_llm_client import FakeLLMClient
from tests.fakes.fake_market_data_provider import FakeMarketDataProvider
from tests.fakes.fake_news_provider import FakeNewsProvider

START, END = date(2026, 1, 5), date(2026, 3, 31)
# Three moves over 2%: +5.0%, -4.0%, +3.0%, each with its own news window
CLOSES = [100, 105, 105, 100.8, 100.8, 103.824, 103.824]
MOVES = 3
TIERS = 3
COMPANY_QUERY = "Acme Corp (ACME) stock news"
INDUSTRY_QUERY = "Widgets industry news, including Globex, Initech"


def market_data(*tickers: str) -> FakeMarketDataProvider:
    tickers = tickers or ("ACME",)
    frames = {t: price_frame(CLOSES) for t in tickers} | {MARKET_TICKER: price_frame([400] * len(CLOSES))}
    profiles = {t: Profile(t, f"{t.title()} Corp", None, "Widgets", None) for t in tickers}
    return FakeMarketDataProvider(frames, profiles)


def llm_reply(user_prompt, response_model):
    if response_model is PeersOutput:
        return PeersOutput(peers=["Globex", "Initech"])
    ids = [int(chunk.split("]")[0]) for chunk in user_prompt.split("[id=")[1:]]
    return ExplanationOutput(
        summary="Acme moved on company news.",
        category=ExplanationCategory.COMPANY,
        confidence=0.8,
        article_relevance=[ArticleRelevance(article_id=i, relevance=0.9) for i in ids],
    )


def explanation_calls(llm: FakeLLMClient) -> int:
    return sum(1 for *_, model in llm.calls if model is ExplanationOutput)


def news_by_tier(query: str):
    if query == MACRO_QUERY:
        return [article_hit("fed-holds-rates")]
    if "industry" in query:
        return [article_hit("globex-recall")]
    return [article_hit("acme-earnings")]


def ingest(session, news, llm, ticker="ACME", limit=25, data=None, refresh=False) -> IngestJob:
    job = create_job(session, ticker, {})
    session.commit()
    run_ingest(SessionLocal, job.id, ticker, START, END, 2.0, limit, data or market_data(ticker), news, llm, refresh)
    session.expire_all()
    return session.get(IngestJob, job.id)


def test_full_run_searches_every_tier_and_explains_every_movement(session):
    news, llm = FakeNewsProvider(responder=news_by_tier), FakeLLMClient(llm_reply)
    job = ingest(session, news, llm)

    assert (job.status, job.stage, job.error) == (JobStatus.DONE, IngestStage.COMPLETE, None)
    assert job.detail["movements"] == MOVES and job.detail["explained"] == MOVES and job.detail["errors"] == []
    assert job.detail["news"] == {
        "searches_run": MOVES * TIERS,
        "searches_cached": 0,
        "cost_dollars": pytest.approx(0.063),
    }
    assert set(news.queries()) == {COMPANY_QUERY, INDUSTRY_QUERY, MACRO_QUERY}
    assert session.query(Explanation).count() == MOVES and session.query(Article).count() == TIERS

    links = session.query(MovementArticle).all()
    assert len(links) == MOVES * TIERS and {ln.relevance for ln in links} == {0.9}
    tier_by_slug = {ln.article.url.rsplit("/", 1)[1]: ln.tier for ln in links}
    assert tier_by_slug == {
        "acme-earnings": NewsTier.COMPANY,
        "globex-recall": NewsTier.INDUSTRY,
        "fed-holds-rates": NewsTier.MACRO,
    }


def test_prompt_shows_each_article_with_the_tier_that_found_it(session):
    llm = FakeLLMClient(llm_reply)
    ingest(session, FakeNewsProvider(responder=news_by_tier), llm)
    prompt = next(user for _, user, model in llm.calls if model is ExplanationOutput)
    assert "found by: company search" in prompt and "found by: industry search" in prompt
    assert "found by: macro search" in prompt


def test_rerun_makes_no_paid_calls(session):
    news, llm = FakeNewsProvider([article_hit("acme-a")]), FakeLLMClient(llm_reply)
    ingest(session, news, llm)
    calls_after_first = (len(news.calls), len(llm.calls))

    job = ingest(session, news, llm)
    assert (len(news.calls), len(llm.calls)) == calls_after_first
    assert job.status is JobStatus.DONE and job.detail["selected"] == 0 and job.detail["explained"] == 0
    assert session.query(Movement).count() == MOVES and session.query(NewsSearchCache).count() == MOVES * TIERS


def test_macro_searches_are_shared_across_tickers(session):
    news, llm = FakeNewsProvider(responder=news_by_tier), FakeLLMClient(llm_reply)
    ingest(session, news, llm, ticker="ACME")
    macro_calls_after_first = news.queries().count(MACRO_QUERY)

    job = ingest(session, news, llm, ticker="BETA")
    assert news.queries().count(MACRO_QUERY) == macro_calls_after_first == MOVES
    assert job.detail["news"]["searches_cached"] == MOVES and job.detail["news"]["searches_run"] == MOVES * 2
    beta_macro_links = (
        session.query(MovementArticle)
        .join(Movement, Movement.id == MovementArticle.movement_id)
        .filter(Movement.ticker == "BETA", MovementArticle.tier == NewsTier.MACRO)
        .count()
    )
    assert beta_macro_links == MOVES  # cached macro articles are linked to the new ticker's movements


def test_refresh_re_explains_without_repeating_cached_searches(session):
    news, llm = FakeNewsProvider(responder=news_by_tier), FakeLLMClient(llm_reply)
    ingest(session, news, llm)
    job = ingest(session, news, llm, refresh=True)
    assert job.detail["explained"] == MOVES and explanation_calls(llm) == MOVES * 2
    assert len(news.calls) == MOVES * TIERS and job.detail["news"]["searches_cached"] == MOVES * TIERS
    assert session.query(Explanation).count() == MOVES


def test_peers_are_suggested_once_and_cached_on_the_company(session):
    news, llm = FakeNewsProvider(), FakeLLMClient(llm_reply)
    ingest(session, news, llm)
    ingest(session, news, llm, refresh=True)
    assert session.get(Company, "ACME").peers == ["Globex", "Initech"]
    assert sum(1 for *_, model in llm.calls if model is PeersOutput) == 1


def test_failed_peer_suggestion_falls_back_to_the_industry_string(session):
    def no_peers(user_prompt, response_model):
        if response_model is PeersOutput:
            raise ProviderError("rate limited")
        return llm_reply(user_prompt, response_model)

    news = FakeNewsProvider()
    job = ingest(session, news, FakeLLMClient(no_peers))
    assert job.status is JobStatus.DONE and "Widgets industry news" in news.queries()
    assert session.get(Company, "ACME").peers is None  # not cached, so the next ingest tries again


def test_cost_guard_limits_paid_work_to_the_largest_moves(session):
    news, llm = FakeNewsProvider([article_hit("acme-a")]), FakeLLMClient(llm_reply)
    ingest(session, news, llm, limit=2)
    explained = {m.pct_change for m in session.query(Movement) if m.explanation}
    assert explained == {5.0, -4.0} and len(news.calls) == 2 * TIERS


def test_one_failed_explanation_does_not_fail_the_job_and_is_retried_next_time(session):
    failures = {"left": 1}

    def flaky(user_prompt, response_model):
        if response_model is ExplanationOutput and "Date: 2026-01-06" in user_prompt and failures["left"]:
            failures["left"] -= 1
            raise ProviderError("rate limited")
        return llm_reply(user_prompt, response_model)

    news = FakeNewsProvider([article_hit("acme-a")])
    job = ingest(session, news, FakeLLMClient(flaky))
    assert job.status is JobStatus.DONE and job.detail["explained"] == MOVES - 1
    assert job.detail["errors"] == ["2026-01-06: rate limited"]

    retry = ingest(session, news, FakeLLMClient(flaky))
    assert retry.detail["explained"] == 1 and len(news.calls) == MOVES * TIERS  # news came from the cache
    assert session.query(Explanation).count() == MOVES


def test_failed_news_search_still_lets_the_movement_be_explained(session):
    class BrokenNews(FakeNewsProvider):
        def search(self, query, start, end, limit):
            raise ProviderError("exa down")

    job = ingest(session, BrokenNews(), FakeLLMClient(llm_reply))
    assert job.status is JobStatus.DONE and job.detail["explained"] == MOVES
    assert len(job.detail["errors"]) == MOVES * TIERS
    assert session.query(NewsSearchCache).count() == 0  # failures aren't cached, so the next ingest retries them


def test_unknown_ticker_fails_the_job_cleanly(session):
    job = ingest(session, FakeNewsProvider(), FakeLLMClient(llm_reply), data=FakeMarketDataProvider({}))
    assert job.status is JobStatus.FAILED and "No price data" in job.error
    assert job.finished_at is not None and session.query(Movement).count() == 0


def test_active_and_latest_job_lookups(session):
    first = create_job(session, "ACME", {"threshold": 2.0})
    session.commit()
    assert get_active_job(session, "ACME").id == first.id
    ingest(session, FakeNewsProvider(), FakeLLMClient(llm_reply))
    assert get_latest_job(session, "ACME").id > first.id
