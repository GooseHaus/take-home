from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy.orm import Session, sessionmaker

from app.api.responses import INVALID_TICKER, MOVEMENT_NOT_FOUND, NOT_INGESTED, PROVIDER_UNAVAILABLE
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
    MovementListResponse,
    MovementResponse,
    PriceListResponse,
    PriceQuery,
    TickerDataQuery,
    TickerDataResponse,
    TickerSummaryResponse,
)
from app.schemas.movement_filters import MovementFilters
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
    responses={200: {"model": IngestJobResponse, "description": "An ingest is already running"}}
    | INVALID_TICKER
    | PROVIDER_UNAVAILABLE,
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


@router.get(
    "/{ticker}/status",
    response_model=IngestJobResponse,
    summary="Latest ingest job for a ticker",
    responses=NOT_INGESTED | INVALID_TICKER,
)
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
    responses=NOT_INGESTED | INVALID_TICKER,
)
def get_ticker(
    ticker: str,
    session: SessionDep,
    query: Annotated[TickerDataQuery, Query()],
):
    """Movement-level filters (dates, direction, size, category, driver_hint, confidence) choose which movements are
    returned. Article-level filters shape the article list inside each movement.

    By default each movement carries only the articles its explanation cited, without text excerpts, which keeps a
    year of data near 100 KB. `articles=all` and `include_snippets=true` return the rest. The same data is also
    available in parts: `/tickers/{ticker}/movements`, `/tickers/{ticker}/prices` and
    `/tickers/{ticker}/movements/{day}`."""
    ticker = ticker_data.normalize_ticker(ticker)
    return ticker_data.get_ticker_data(session, ticker, query.movement_filters(), query.include_prices)


@router.get(
    "/{ticker}/movements",
    response_model=MovementListResponse,
    summary="A ticker's major movements with explanations and articles, filtered and paginated",
    responses=NOT_INGESTED | INVALID_TICKER,
)
def list_movements(ticker: str, session: SessionDep, filters: Annotated[MovementFilters, Query()]):
    return ticker_data.get_movements(session, ticker_data.normalize_ticker(ticker), filters)


@router.get(
    "/{ticker}/prices",
    response_model=PriceListResponse,
    summary="Daily price bars for the analysed period, or for a date range",
    responses=NOT_INGESTED | INVALID_TICKER,
)
def list_prices(ticker: str, session: SessionDep, query: Annotated[PriceQuery, Query()]):
    """Prices are split- and dividend-adjusted. Without dates this returns the period covered by the ticker's
    ingests. The warm-up history stored before it is only returned when asked for by date."""
    return ticker_data.get_prices(session, ticker_data.normalize_ticker(ticker), query.start, query.end)


@router.get(
    "/{ticker}/movements/{day}",
    response_model=MovementResponse,
    summary="One movement in full: stats, explanation and every article considered, with excerpts",
    responses=MOVEMENT_NOT_FOUND | INVALID_TICKER,
)
def get_movement(ticker: str, day: date, session: SessionDep):
    return ticker_data.get_movement_detail(session, ticker_data.normalize_ticker(ticker), day)
