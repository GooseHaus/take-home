"""yfinance access: daily bars + company profile. The only module that talks to Yahoo."""

from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.domain.profile import Profile
from app.errors.ticker_not_found import TickerNotFound
from app.models import Company, Price

MARKET_TICKER = "SPY"

# yfinance sector name -> SPDR sector ETF
SECTOR_ETFS = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}

# Extra history fetched before the requested start so trailing-volatility stats are warm on day one
WARMUP_DAYS = 100


def fetch_history(ticker: str, start: date, end: date) -> pd.DataFrame:
    """Daily bars indexed by date, columns open/high/low/close/volume.

    auto_adjust=True: split- and dividend-adjusted, so a 4:1 split isn't detected as a -75% "movement".
    """
    df = yf.Ticker(ticker).history(
        start=start - timedelta(days=WARMUP_DAYS),
        end=end + timedelta(days=1),  # yfinance end is exclusive
        interval="1d",
        auto_adjust=True,
    )
    if df.empty:
        raise TickerNotFound(f"No price data for '{ticker}'")
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
    df.index = pd.Index([ts.date() for ts in df.index], name="date")
    return df


def fetch_profile(ticker: str) -> Profile:
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        # .info is Yahoo's flakiest endpoint; a missing profile only weakens news queries
        info = {}
    sector = info.get("sector")
    return Profile(
        ticker=ticker,
        name=info.get("longName") or info.get("shortName") or ticker,
        sector=sector,
        industry=info.get("industry"),
        sector_etf=SECTOR_ETFS.get(sector),
    )


def store_prices(session: Session, ticker: str, df: pd.DataFrame) -> int:
    rows = [
        {
            "ticker": ticker,
            "date": d,
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": int(r.volume),
        }
        for d, r in df.iterrows()
    ]
    if not rows:
        return 0
    # Chunked: SQLite caps bound variables per statement
    for i in range(0, len(rows), 500):
        stmt = insert(Price).values(rows[i : i + 500])
        # Adjusted closes shift after each dividend, so refresh existing rows rather than skipping them
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "date"],
            set_={c: stmt.excluded[c] for c in ("open", "high", "low", "close", "volume")},
        )
        session.execute(stmt)
    return len(rows)


def store_profile(session: Session, profile: Profile) -> Company:
    company = session.get(Company, profile.ticker) or Company(ticker=profile.ticker)
    company.name = profile.name
    company.sector = profile.sector
    company.industry = profile.industry
    company.sector_etf = profile.sector_etf
    session.add(company)
    return company


def load_prices(session: Session, ticker: str) -> pd.DataFrame:
    rows = session.query(Price).filter(Price.ticker == ticker).order_by(Price.date).all()
    return pd.DataFrame(
        {"close": [r.close for r in rows], "volume": [r.volume for r in rows]},
        index=pd.Index([r.date for r in rows], name="date"),
    )
