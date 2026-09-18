from dataclasses import dataclass


@dataclass
class Profile:
    """Company profile as fetched from the market-data provider, before it is persisted."""

    ticker: str
    name: str
    sector: str | None
    industry: str | None
    sector_etf: str | None
