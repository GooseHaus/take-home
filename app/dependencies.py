"""Wiring: the one place that decides which concrete adapter backs each Protocol. Tests override these via
`app.dependency_overrides`."""

from functools import lru_cache

from app.config import get_settings
from app.providers.market_data import MarketDataProvider, YFinanceMarketDataProvider
from app.providers.news import ExaNewsProvider, NewsProvider


@lru_cache
def get_market_data_provider() -> MarketDataProvider:
    return YFinanceMarketDataProvider()


@lru_cache
def get_news_provider() -> NewsProvider:
    return ExaNewsProvider(get_settings().exa_api_key)
