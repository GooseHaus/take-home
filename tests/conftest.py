import os

# Set before app.config and app.db are imported. Environment variables take priority over .env, so tests never use
# data/app.db or real API keys, and they behave the same locally as in CI. A test that needs a provider injects a fake.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["EXA_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""

import pytest  # noqa: E402

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402


@pytest.fixture
def session():
    """A session on a freshly created schema; everything is dropped afterwards so tests stay independent."""
    init_db()
    with SessionLocal() as s:
        yield s
    Base.metadata.drop_all(engine)
