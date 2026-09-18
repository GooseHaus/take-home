"""Wiring: the one place that decides which concrete adapter backs each Protocol. Tests override these via
`app.dependency_overrides`."""

from functools import lru_cache

from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import SessionLocal
from app.providers.llm import LLMClient, OpenAILLMClient
from app.providers.market_data import MarketDataProvider, YFinanceMarketDataProvider
from app.providers.news import ExaNewsProvider, NewsProvider


def get_session_factory() -> sessionmaker:
    """For background work that outlives the request and so must open its own sessions."""
    return SessionLocal


@lru_cache
def get_market_data_provider() -> MarketDataProvider:
    return YFinanceMarketDataProvider()


@lru_cache
def get_news_provider() -> NewsProvider:
    return ExaNewsProvider(get_settings().exa_api_key)


@lru_cache
def get_llm_client() -> LLMClient:
    settings = get_settings()
    return OpenAILLMClient(settings.openai_api_key, settings.openai_model)
