from dataclasses import dataclass


@dataclass(frozen=True)
class Peer:
    """A competitor. `ticker` is None when no listed symbol is known, in which case only news search uses it."""

    name: str
    ticker: str | None = None
