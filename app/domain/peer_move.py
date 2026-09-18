from dataclasses import dataclass


@dataclass(frozen=True)
class PeerMove:
    """A competitor's close-to-close change on the day of a movement."""

    name: str
    ticker: str
    pct_change: float
