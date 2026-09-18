import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from app.constants.market import SECTOR_ETFS
from app.domain import Profile
from app.errors import TickerNotFound

logger = logging.getLogger(__name__)

PRICE_COLUMNS = ["open", "high", "low", "close", "volume"]


class YFinanceMarketDataProvider:
    def fetch_history(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        # auto_adjust=True: split/dividend-adjusted, so a 4:1 split isn't detected as a -75% "movement" (D12)
        df = yf.Ticker(ticker).history(
            start=start,
            end=end + timedelta(days=1),  # yfinance end is exclusive
            interval="1d",
            auto_adjust=True,
        )
        if df.empty:
            raise TickerNotFound(f"No price data for '{ticker}'")
        df = df.rename(columns=str.lower)[PRICE_COLUMNS].dropna(subset=["close"])
        df.index = pd.Index([ts.date() for ts in df.index], name="date")
        return df

    def fetch_profile(self, ticker: str) -> Profile:
        try:
            info = yf.Ticker(ticker).info or {}
        except Exception:
            # .info is Yahoo's flakiest endpoint; a missing profile only weakens news queries
            logger.warning("Profile lookup failed for %s; continuing with ticker as name", ticker, exc_info=True)
            info = {}
        sector = info.get("sector")
        return Profile(
            ticker=ticker,
            name=info.get("longName") or info.get("shortName") or ticker,
            sector=sector,
            industry=info.get("industry"),
            sector_etf=SECTOR_ETFS.get(sector),
        )
