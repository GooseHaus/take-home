"""Wiring: the one place that decides which concrete adapter backs each Protocol. Tests override these via
`app.dependency_overrides`."""

from functools import lru_cache

from app.providers.market_data import MarketDataProvider, YFinanceMarketDataProvider


@lru_cache
def get_market_data_provider() -> MarketDataProvider:
    return YFinanceMarketDataProvider()
