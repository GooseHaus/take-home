"""Assemble stored data into API shapes. Shared by the REST endpoints and the chat tools."""

import re
from datetime import date

from sqlalchemy.orm import Session

from app.constants.api import TICKER_PATTERN
from app.constants.llm import CITATION_MIN_RELEVANCE
from app.domain import PeerMove
from app.enums import ArticleScope
from app.errors import InvalidTicker, MovementNotFound, TickerNotIngested
from app.models import Company, Movement, MovementArticle
from app.repositories import movement_queries
from app.repositories.ingest_jobs import analysed_period, get_latest_job
from app.schemas.api import (
    ArticleResponse,
    CompanyResponse,
    ExplanationResponse,
    IngestJobResponse,
    MovementListResponse,
    MovementResponse,
    PeerMoveResponse,
    PeerResponse,
    PriceListResponse,
    PriceResponse,
    TickerDataResponse,
    TickerSummaryResponse,
)
from app.schemas.movement_filters import MovementFilters
from app.services.peers import company_peers, load_peer_returns, peer_moves_on

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


def is_cited(link: MovementArticle) -> bool:
    return (link.relevance or 0.0) >= CITATION_MIN_RELEVANCE


def to_article_responses(movement: Movement, filters: MovementFilters) -> list[ArticleResponse]:
    """A movement's articles, most relevant first, shaped by the article-level filters."""
    if filters.articles is ArticleScope.NONE:
        return []
    articles = []
    for link in movement.article_links:
        if filters.articles is ArticleScope.CITED and not is_cited(link):
            continue
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
                snippet=article.snippet if filters.include_snippets else None,
                tier=link.tier,
                relevance=link.relevance,
                cited=is_cited(link),
            )
        )
    return sorted(articles, key=lambda a: a.relevance or 0.0, reverse=True)


def to_company_response(company: Company) -> CompanyResponse:
    return CompanyResponse(
        ticker=company.ticker,
        name=company.name,
        sector=company.sector,
        industry=company.industry,
        sector_etf=company.sector_etf,
        peers=[PeerResponse.model_validate(peer) for peer in company_peers(company)],
    )


def to_movement_response(movement: Movement, filters: MovementFilters, peer_moves: list[PeerMove]) -> MovementResponse:
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
        peer_moves=[PeerMoveResponse.model_validate(move) for move in peer_moves],
        explanation=ExplanationResponse.model_validate(explanation) if explanation else None,
        articles=to_article_responses(movement, filters),
    )


def price_window(
    session: Session, ticker: str, start: date | None, end: date | None
) -> tuple[date | None, date | None]:
    """The dates prices are read for: what the caller asked for, else the analysed period.

    Stored prices begin about three months before the first ingest window, as warm-up for the volatility stats.
    That history was never analysed for movements, so it is left out unless asked for by date.
    """
    period = analysed_period(session, ticker)
    if period is None:
        return start, end
    return start or period[0], end or period[1]


def get_ticker_summary(session: Session, company: Company) -> TickerSummaryResponse:
    window = price_window(session, company.ticker, None, None)
    first, last = movement_queries.price_date_range(session, company.ticker, *window)
    total, explained = movement_queries.movement_counts(session, company.ticker)
    return TickerSummaryResponse(
        company=to_company_response(company),
        first_price_date=first,
        last_price_date=last,
        movement_count=total,
        explained_count=explained,
    )


def list_ticker_summaries(session: Session) -> list[TickerSummaryResponse]:
    return [get_ticker_summary(session, company) for company in movement_queries.list_companies(session)]


def get_prices(session: Session, ticker: str, start: date | None, end: date | None) -> PriceListResponse:
    require_company(session, ticker)
    window = price_window(session, ticker, start, end)
    prices = movement_queries.get_prices(session, ticker, *window)
    return PriceListResponse(
        ticker=ticker, start=window[0], end=window[1], prices=[PriceResponse.model_validate(p) for p in prices]
    )


def get_movements(session: Session, ticker: str, filters: MovementFilters) -> MovementListResponse:
    company = require_company(session, ticker)
    movements, total = movement_queries.query_movements(session, ticker, filters)
    peers = company_peers(company)
    peer_returns = load_peer_returns(session, peers)
    return MovementListResponse(
        ticker=ticker,
        filters=filters,
        total_movements=total,
        movements=[to_movement_response(m, filters, peer_moves_on(m.date, peers, peer_returns)) for m in movements],
    )


def get_ticker_data(
    session: Session, ticker: str, filters: MovementFilters, include_prices: bool = True
) -> TickerDataResponse:
    """The brief's "all stock and news data" response: the summary, the movements and, optionally, the prices."""
    company = require_company(session, ticker)
    listing = get_movements(session, ticker, filters)
    latest_job = get_latest_job(session, ticker)
    prices = get_prices(session, ticker, filters.start, filters.end).prices if include_prices else None
    return TickerDataResponse(
        summary=get_ticker_summary(session, company),
        latest_ingest=IngestJobResponse.model_validate(latest_job) if latest_job else None,
        filters=filters,
        total_movements=listing.total_movements,
        movements=listing.movements,
        prices=prices,
    )


# The single-movement view is the place to see everything that was considered, excerpts included
DETAIL_FILTERS = MovementFilters(articles=ArticleScope.ALL, include_snippets=True)


def get_movement_detail(session: Session, ticker: str, day: date) -> MovementResponse:
    company = require_company(session, ticker)
    movement = movement_queries.get_movement(session, ticker, day)
    if movement is None:
        raise MovementNotFound(f"{ticker} has no major movement on {day}")
    peers = company_peers(company)
    peer_moves = peer_moves_on(movement.date, peers, load_peer_returns(session, peers))
    return to_movement_response(movement, DETAIL_FILTERS, peer_moves)
