"""Movement detection. Pure functions over price series: no I/O, no database."""

from datetime import date, timedelta

import pandas as pd

from app.domain.detected_movement import DetectedMovement

VOL_WINDOW = 60  # trading days of trailing returns behind the z-score
VOL_MIN_PERIODS = 20
VOLUME_WINDOW = 20

# A benchmark "explains" a move when it went the same way, moved meaningfully in its own right,
# and covers a fair share of the stock's move (high-beta names amplify the market, so not 1:1).
BENCHMARK_MIN_ABS_PCT = 1.0
BENCHMARK_MIN_SHARE = 0.4

# Published-date bounds are hard filters in the news API, so catch next-day write-ups too (D5)
WINDOW_TRAILING_DAYS = 1


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


def driver_hint(pct: float, market_pct: float | None, sector_pct: float | None) -> str:
    """Which news tier most likely explains the move (D4). A hint for ordering and prompting, never a filter."""
    if benchmark_explains(pct, market_pct):
        return "market"
    if benchmark_explains(pct, sector_pct):
        return "sector"
    return "idiosyncratic"


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
) -> list[DetectedMovement]:
    """Days where |close-to-close change| >= threshold_pct (D3).

    `prices`/`market`/`sector` are date-indexed frames with `close` (and `volume` for prices).
    Stats use all supplied history; only days inside [start, end] are reported.
    """
    close = prices["close"]
    returns = pct_returns(close)
    zscores = trailing_zscore(returns)
    avg_volume = prices["volume"].shift(1).rolling(VOLUME_WINDOW, min_periods=5).mean()
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
        if pd.isna(pct) or round(abs(pct), 4) < threshold_pct:
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
                pct_change=round(float(pct), 4),
                zscore=_optional(zscores.iloc[i]),
                volume_ratio=_optional(volume_ratio.iloc[i]),
                market_pct_change=market_pct,
                sector_pct_change=sector_pct,
                excess_vs_market=None if market_pct is None else round(float(pct) - market_pct, 4),
                excess_vs_sector=None if sector_pct is None else round(float(pct) - sector_pct, 4),
                driver_hint=driver_hint(float(pct), market_pct, sector_pct),
                window_start=window_start,
                window_end=window_end,
            )
        )
    return movements
