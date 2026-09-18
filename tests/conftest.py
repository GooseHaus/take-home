import os

# Must be set before app.config / app.db are imported. Environment variables outrank .env, so this makes the suite
# hermetic: it never touches data/app.db, and it behaves the same on a developer machine with real keys as on a
# fresh clone or in CI with none. Anything that needs a provider must inject a fake.
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
