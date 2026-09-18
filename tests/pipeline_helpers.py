"""Shared by the pipeline, peer and database tests: a small ACME price history, scripted fakes, and `ingest`."""

from datetime import date

from app.constants.market import MARKET_TICKER
from app.constants.news import MACRO_QUERY
from app.db import SessionLocal
from app.domain import Profile
from app.enums import ExplanationCategory
from app.models import IngestJob
from app.repositories.ingest_jobs import create_job
from app.schemas.llm import ArticleRelevance, ExplanationOutput, PeersOutput, PeerSuggestion
from app.services.pipeline import run_ingest
from tests.factories import article_hit, price_frame
from tests.fakes.fake_llm_client import FakeLLMClient
from tests.fakes.fake_market_data_provider import FakeMarketDataProvider

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
        return PeersOutput(
            peers=[PeerSuggestion(name="Globex", ticker="GLBX"), PeerSuggestion(name="Initech", ticker=None)]
        )
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


def ingest(session, news, llm, ticker="ACME", limit=25, data=None, refresh=False, now=None) -> IngestJob:
    """`now` defaults to the real clock, which is months after the test windows, so their searches count as settled."""
    job = create_job(session, ticker, {})
    session.commit()
    provider = data or market_data(ticker)
    run_ingest(SessionLocal, job.id, ticker, START, END, 2.0, limit, provider, news, llm, refresh, now)
    session.expire_all()
    return session.get(IngestJob, job.id)
