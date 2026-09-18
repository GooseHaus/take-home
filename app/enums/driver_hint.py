from enum import StrEnum


class DriverHint(StrEnum):
    """What the price data alone suggests drove a move (D4)."""

    MARKET = "market"
    SECTOR = "sector"
    IDIOSYNCRATIC = "idiosyncratic"
