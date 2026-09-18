"""Builders for test data. Keep seed-shape knowledge here, not scattered through tests."""

from datetime import date, timedelta

import pandas as pd


def trading_days(start: date, count: int) -> list[date]:
    days, day = [], start
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def price_frame(closes: list[float], start: date = date(2026, 1, 5), volumes: list[int] | None = None) -> pd.DataFrame:
    """Date-indexed OHLCV frame over consecutive weekdays; open/high/low mirror close."""
    index = pd.Index(trading_days(start, len(closes)), name="date")
    volumes = volumes or [1_000] * len(closes)
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": volumes}, index=index
    )
