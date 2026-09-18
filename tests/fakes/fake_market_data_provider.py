from datetime import date

import pandas as pd

from app.domain import Profile
from app.errors import TickerNotFound


class FakeMarketDataProvider:
    """In-memory MarketDataProvider. `frames` maps ticker -> date-indexed OHLCV frame."""

    def __init__(self, frames: dict[str, pd.DataFrame], profiles: dict[str, Profile] | None = None):
        self.frames = frames
        self.profiles = profiles or {}
        self.history_calls: list[tuple[str, date, date]] = []

    def fetch_history(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        self.history_calls.append((ticker, start, end))
        if ticker not in self.frames:
            raise TickerNotFound(f"No price data for '{ticker}'")
        return self.frames[ticker]

    def fetch_profile(self, ticker: str) -> Profile:
        return self.profiles.get(ticker) or Profile(ticker, ticker, None, None, None)
