from dataclasses import dataclass
from datetime import date

from app.enums import DriverHint


@dataclass
class DetectedMovement:
    """A major single-day move, as computed from price series, before it is persisted."""

    date: date
    close: float
    prev_close: float
    pct_change: float
    zscore: float | None
    volume_ratio: float | None
    market_pct_change: float | None
    sector_pct_change: float | None
    excess_vs_market: float | None
    excess_vs_sector: float | None
    driver_hint: DriverHint
    window_start: date
    window_end: date
