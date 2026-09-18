"""Movement detection. Pure functions over price series: no I/O, no database."""

from datetime import date, timedelta

import pandas as pd

from app.constants.movements import (
    BENCHMARK_MIN_ABS_PCT,
    BENCHMARK_MIN_SHARE,
    MIN_PEERS_FOR_HINT,
    PCT_DECIMALS,
    VOL_MIN_PERIODS,
    VOL_WINDOW,
    VOLUME_MIN_PERIODS,
    VOLUME_WINDOW,
    WINDOW_TRAILING_DAYS,
)
from app.domain import DetectedMovement
from app.enums import DriverHint


def pct_returns(close: pd.Series) -> pd.Series:
    return close.pct_change() * 100


def trailing_zscore(returns: pd.Series) -> pd.Series:
    # shift(1): the day being scored must not dampen its own z-score
    vol = returns.shift(1).rolling(VOL_WINDOW, min_periods=VOL_MIN_PERIODS).std()
    return returns / vol


def benchmark_explains(pct: float, benchmark_pct: float | None) -> bool:
    if benchmark_pct is None:
        return False
    same_direction = pct * benchmark_pct > 0
    needed = max(BENCHMARK_MIN_ABS_PCT, BENCHMARK_MIN_SHARE * abs(pct))
    return same_direction and abs(benchmark_pct) >= needed


def driver_hint(
    pct: float, market_pct: float | None, sector_pct: float | None, peer_median_pct: float | None = None
) -> DriverHint:
    """Which news tier most likely explains the move (D4). A hint for ordering and prompting, never a filter.

    Direct competitors moving together count as a sector move even when the broad sector ETF did not (D20).
    """
    if benchmark_explains(pct, market_pct):
        return DriverHint.MARKET
    if benchmark_explains(pct, sector_pct) or benchmark_explains(pct, peer_median_pct):
        return DriverHint.SECTOR
    return DriverHint.IDIOSYNCRATIC


def peer_median(day: date, peer_returns: dict[str, pd.Series] | None) -> float | None:
    """Median same-day return of the peers that traded that day. None with fewer than MIN_PEERS_FOR_HINT values."""
    values = [s[day] for s in (peer_returns or {}).values() if day in s.index and not pd.isna(s[day])]
    if len(values) < MIN_PEERS_FOR_HINT:
        return None
    return float(pd.Series(values).median())


def news_window(day: date, prev_trading_day: date) -> tuple[date, date]:
    """Previous trading day through the move day (+ trailing buffer).

    Starting at the previous session covers after-hours earnings and, for a Monday move, the whole weekend.
    """
    return prev_trading_day, day + timedelta(days=WINDOW_TRAILING_DAYS)


def _optional(value) -> float | None:
    return None if value is None or pd.isna(value) else float(value)


def detect_movements(
    prices: pd.DataFrame,
    market: pd.DataFrame | None,
    sector: pd.DataFrame | None,
    threshold_pct: float,
    start: date | None = None,
    end: date | None = None,
    peer_returns: dict[str, pd.Series] | None = None,
) -> list[DetectedMovement]:
    """Days where |close-to-close change| >= threshold_pct (D3).

    `prices`/`market`/`sector` are date-indexed frames with `close` (and `volume` for prices).
    Stats use all supplied history; only days inside [start, end] are reported.
    """
    close = prices["close"]
    returns = pct_returns(close)
    zscores = trailing_zscore(returns)
    avg_volume = prices["volume"].shift(1).rolling(VOLUME_WINDOW, min_periods=VOLUME_MIN_PERIODS).mean()
    volume_ratio = prices["volume"] / avg_volume

    def benchmark_returns(frame: pd.DataFrame | None) -> pd.Series:
        if frame is None or frame.empty:
            return pd.Series(dtype=float)
        return pct_returns(frame["close"])

    market_returns = benchmark_returns(market)
    sector_returns = benchmark_returns(sector)

    dates = list(prices.index)
    movements = []
    for i in range(1, len(dates)):
        day = dates[i]
        pct = returns.iloc[i]
        # Rounded so float noise (1.9999999) can't drop a day sitting exactly on the threshold
        if pd.isna(pct) or round(abs(pct), PCT_DECIMALS) < threshold_pct:
            continue
        if (start and day < start) or (end and day > end):
            continue

        market_pct = _optional(market_returns.get(day))
        sector_pct = _optional(sector_returns.get(day))
        window_start, window_end = news_window(day, dates[i - 1])
        movements.append(
            DetectedMovement(
                date=day,
                close=float(close.iloc[i]),
                prev_close=float(close.iloc[i - 1]),
                pct_change=round(float(pct), PCT_DECIMALS),
                zscore=_optional(zscores.iloc[i]),
                volume_ratio=_optional(volume_ratio.iloc[i]),
                market_pct_change=market_pct,
                sector_pct_change=sector_pct,
                excess_vs_market=None if market_pct is None else round(float(pct) - market_pct, PCT_DECIMALS),
                excess_vs_sector=None if sector_pct is None else round(float(pct) - sector_pct, PCT_DECIMALS),
                driver_hint=driver_hint(float(pct), market_pct, sector_pct, peer_median(day, peer_returns)),
                window_start=window_start,
                window_end=window_end,
            )
        )
    return movements
