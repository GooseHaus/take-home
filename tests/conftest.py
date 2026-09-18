import os

# Set before app.config and app.db are imported. Environment variables take priority over .env, so tests never use
# data/app.db or real API keys, and they behave the same locally as in CI. A test that needs a provider injects a fake.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["EXA_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""

import pytest  # noqa: E402

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402
from app.dependencies import get_llm_client, get_market_data_provider, get_news_provider  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_providers():
    """The provider factories are cached for the life of the process. Clear them so no test sees another's client."""
    for factory in (get_market_data_provider, get_news_provider, get_llm_client):
        factory.cache_clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def session():
    """A session on a freshly created schema; everything is dropped afterwards so tests stay independent."""
    init_db()
    with SessionLocal() as s:
        yield s
    Base.metadata.drop_all(engine)
