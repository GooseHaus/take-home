from datetime import date
from typing import Protocol

import pandas as pd

from app.domain import Profile


class MarketDataProvider(Protocol):
    """Source of daily price bars and company profiles."""

    def fetch_history(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        """Adjusted daily bars for [start, end], date-indexed, columns open/high/low/close/volume.

        Raises TickerNotFound when the ticker has no data.
        """
        ...

    def fetch_profile(self, ticker: str) -> Profile: ...
