"""Pull a ticker and its benchmarks from the market-data provider into the database."""

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.constants.market import MARKET_TICKER, SECTOR_ETFS, WARMUP_DAYS
from app.models import Company
from app.providers.market_data import MarketDataProvider
from app.repositories.companies import upsert_company
from app.repositories.prices import upsert_prices

logger = logging.getLogger(__name__)


def benchmark_tickers(company: Company) -> list[str]:
    return [t for t in (MARKET_TICKER, company.sector_etf) if t]


def ingest_prices(session: Session, provider: MarketDataProvider, ticker: str, start: date, end: date) -> Company:
    """Fetch everything first, then write and commit.

    SQLite has one write lock. Writing between fetches would hold it for the length of several network calls and
    make every other request that writes (chat, another ticker's ingest) fail with "database is locked".
    An unknown ticker fails on the first fetch, before anything is written.
    """
    fetch_start = start - timedelta(days=WARMUP_DAYS)
    bars = {ticker: provider.fetch_history(ticker, fetch_start, end)}
    profile = provider.fetch_profile(ticker)
    for benchmark in (MARKET_TICKER, SECTOR_ETFS.get(profile.sector)):
        if benchmark:
            bars[benchmark] = provider.fetch_history(benchmark, fetch_start, end)

    company = upsert_company(session, profile)
    for symbol, frame in bars.items():
        upsert_prices(session, symbol, frame)
    session.commit()

    logger.info("Ingested %d bars for %s (+ benchmarks %s)", len(bars[ticker]), ticker, benchmark_tickers(company))
    return company
