"""Pull a ticker and its benchmarks from the market-data provider into the database."""

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.constants.market import MARKET_TICKER, WARMUP_DAYS
from app.models import Company
from app.providers.market_data import MarketDataProvider
from app.repositories.companies import upsert_company
from app.repositories.prices import upsert_prices

logger = logging.getLogger(__name__)


def benchmark_tickers(company: Company) -> list[str]:
    return [t for t in (MARKET_TICKER, company.sector_etf) if t]


def ingest_prices(session: Session, provider: MarketDataProvider, ticker: str, start: date, end: date) -> Company:
    """Fetch the ticker first so an unknown ticker fails before anything is written; then profile + benchmarks."""
    fetch_start = start - timedelta(days=WARMUP_DAYS)
    bars = provider.fetch_history(ticker, fetch_start, end)
    company = upsert_company(session, provider.fetch_profile(ticker))
    upsert_prices(session, ticker, bars)

    for benchmark in benchmark_tickers(company):
        upsert_prices(session, benchmark, provider.fetch_history(benchmark, fetch_start, end))

    logger.info("Ingested %d bars for %s (+ benchmarks %s)", len(bars), ticker, benchmark_tickers(company))
    return company
