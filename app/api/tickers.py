from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db import get_session
from app.dependencies import get_llm_client, get_market_data_provider, get_news_provider, get_session_factory
from app.errors import TickerNotIngested
from app.providers.llm import LLMClient
from app.providers.market_data import MarketDataProvider
from app.providers.news import NewsProvider
from app.repositories.ingest_jobs import get_latest_job
from app.schemas.api import (
    IngestJobResponse,
    IngestRequest,
    MovementResponse,
    TickerDataQuery,
    TickerDataResponse,
    TickerSummaryResponse,
)
from app.services import ticker_data
from app.services.ingest_requests import open_job, resolve
from app.services.pipeline import run_ingest

router = APIRouter(prefix="/tickers", tags=["tickers"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("", response_model=list[TickerSummaryResponse], summary="List ingested tickers")
def list_tickers(session: SessionDep):
    return ticker_data.list_ticker_summaries(session)


@router.post(
    "/{ticker}/ingest",
    response_model=IngestJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Fetch prices, detect major movements, find news and explain them (runs in the background)",
)
def ingest_ticker(
    ticker: str,
    background_tasks: BackgroundTasks,
    response: Response,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    session_factory: Annotated[sessionmaker, Depends(get_session_factory)],
    market_data: Annotated[MarketDataProvider, Depends(get_market_data_provider)],
    news: Annotated[NewsProvider, Depends(get_news_provider)],
    llm: Annotated[LLMClient, Depends(get_llm_client)],
    request: IngestRequest | None = None,
):
    """Returns the job to poll at `GET /tickers/{ticker}/status`.

    Safe to repeat: finished work is never redone or re-billed, and an ingest already in flight for the ticker is
    returned (200) rather than started twice. Missing API keys fail here with 503, before any job is created.
    """
    ticker = ticker_data.normalize_ticker(ticker)
    resolved = resolve(request or IngestRequest(), settings)
    job, created = open_job(session, ticker, resolved)
    if created:
        background_tasks.add_task(
            run_ingest,
            session_factory,
            job.id,
            ticker,
            resolved.start,
            resolved.end,
            resolved.threshold_pct,
            resolved.max_movements,
            market_data,
            news,
            llm,
            resolved.refresh,
        )
    else:
        response.status_code = status.HTTP_200_OK
    return job


@router.get("/{ticker}/status", response_model=IngestJobResponse, summary="Latest ingest job for a ticker")
def ingest_status(ticker: str, session: SessionDep):
    ticker = ticker_data.normalize_ticker(ticker)
    job = get_latest_job(session, ticker)
    if job is None:
        raise TickerNotIngested(f"No ingest has been requested for {ticker}. POST /tickers/{ticker}/ingest first.")
    return job


@router.get(
    "/{ticker}",
    response_model=TickerDataResponse,
    summary="All stock and news data for a ticker: prices, major movements, explanations and articles",
)
def get_ticker(
    ticker: str,
    session: SessionDep,
    query: Annotated[TickerDataQuery, Query()],
):
    """Movement-level filters (dates, direction, size, category, driver_hint, confidence) choose which movements are
    returned; article-level filters (`tier`, `min_relevance`) narrow the articles shown inside each movement."""
    ticker = ticker_data.normalize_ticker(ticker)
    return ticker_data.get_ticker_data(
        session, ticker, query.movement_filters(), query.include_prices, query.include_news
    )


@router.get(
    "/{ticker}/movements/{day}",
    response_model=MovementResponse,
    summary="One movement in full: stats, explanation and every article considered",
)
def get_movement(ticker: str, day: date, session: SessionDep):
    return ticker_data.get_movement_detail(session, ticker_data.normalize_ticker(ticker), day)
