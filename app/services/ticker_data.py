"""Assemble stored data into API shapes. Shared by the REST endpoints and the chat tools."""

import re
from datetime import date

from sqlalchemy.orm import Session

from app.constants.api import TICKER_PATTERN
from app.constants.llm import CITATION_MIN_RELEVANCE
from app.errors import InvalidTicker, MovementNotFound, TickerNotIngested
from app.models import Company, Movement
from app.repositories import movement_queries
from app.repositories.ingest_jobs import get_latest_job
from app.schemas.api import (
    ArticleResponse,
    CompanyResponse,
    ExplanationResponse,
    IngestJobResponse,
    MovementResponse,
    PriceResponse,
    TickerDataResponse,
    TickerSummaryResponse,
)
from app.schemas.movement_filters import MovementFilters

_TICKER = re.compile(TICKER_PATTERN)


def normalize_ticker(raw: str) -> str:
    ticker = raw.strip().upper()
    if not _TICKER.match(ticker):
        raise InvalidTicker(f"'{raw}' is not a valid ticker symbol")
    return ticker


def require_company(session: Session, ticker: str) -> Company:
    company = session.get(Company, ticker)
    if company is None:
        raise TickerNotIngested(f"No data for {ticker} yet. POST /tickers/{ticker}/ingest first.")
    return company


def to_article_responses(movement: Movement, filters: MovementFilters) -> list[ArticleResponse]:
    """A movement's articles, most relevant first, narrowed by the article-level filters (tier, min_relevance)."""
    articles = []
    for link in movement.article_links:
        if filters.tier and link.tier is not filters.tier:
            continue
        if filters.min_relevance is not None and (link.relevance or 0.0) < filters.min_relevance:
            continue
        article = link.article
        articles.append(
            ArticleResponse(
                id=article.id,
                url=article.url,
                title=article.title,
                source=article.source,
                published_at=article.published_at,
                snippet=article.snippet,
                tier=link.tier,
                relevance=link.relevance,
                cited=(link.relevance or 0.0) >= CITATION_MIN_RELEVANCE,
            )
        )
    return sorted(articles, key=lambda a: a.relevance or 0.0, reverse=True)


def to_movement_response(movement: Movement, filters: MovementFilters, include_news: bool = True) -> MovementResponse:
    explanation = movement.explanation
    return MovementResponse(
        ticker=movement.ticker,
        date=movement.date,
        pct_change=movement.pct_change,
        close=movement.close,
        prev_close=movement.prev_close,
        zscore=movement.zscore,
        volume_ratio=movement.volume_ratio,
        market_pct_change=movement.market_pct_change,
        sector_pct_change=movement.sector_pct_change,
        excess_vs_market=movement.excess_vs_market,
        excess_vs_sector=movement.excess_vs_sector,
        driver_hint=movement.driver_hint,
        news_window_start=movement.window_start,
        news_window_end=movement.window_end,
        explanation=ExplanationResponse.model_validate(explanation) if explanation else None,
        articles=to_article_responses(movement, filters) if include_news else [],
    )


def get_ticker_summary(session: Session, company: Company) -> TickerSummaryResponse:
    first, last = movement_queries.price_date_range(session, company.ticker)
    total, explained = movement_queries.movement_counts(session, company.ticker)
    return TickerSummaryResponse(
        company=CompanyResponse.model_validate(company),
        first_price_date=first,
        last_price_date=last,
        movement_count=total,
        explained_count=explained,
    )


def list_ticker_summaries(session: Session) -> list[TickerSummaryResponse]:
    return [get_ticker_summary(session, company) for company in movement_queries.list_companies(session)]


def get_ticker_data(
    session: Session, ticker: str, filters: MovementFilters, include_prices: bool = True, include_news: bool = True
) -> TickerDataResponse:
    company = require_company(session, ticker)
    movements, total = movement_queries.query_movements(session, ticker, filters)
    latest_job = get_latest_job(session, ticker)
    prices = movement_queries.get_prices(session, ticker, filters.start, filters.end) if include_prices else None
    return TickerDataResponse(
        summary=get_ticker_summary(session, company),
        latest_ingest=IngestJobResponse.model_validate(latest_job) if latest_job else None,
        filters=filters,
        total_movements=total,
        movements=[to_movement_response(m, filters, include_news) for m in movements],
        prices=[PriceResponse.model_validate(p) for p in prices] if prices is not None else None,
    )


def get_movement_detail(session: Session, ticker: str, day: date) -> MovementResponse:
    require_company(session, ticker)
    movement = movement_queries.get_movement(session, ticker, day)
    if movement is None:
        raise MovementNotFound(f"{ticker} has no major movement on {day}")
    return to_movement_response(movement, MovementFilters())
