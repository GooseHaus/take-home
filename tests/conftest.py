import os

# Must be set before app.db is imported: tests never touch data/app.db or real keys.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest  # noqa: E402

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402


@pytest.fixture
def session():
    """A session on a freshly created schema; everything is dropped afterwards so tests stay independent."""
    init_db()
    with SessionLocal() as s:
        yield s
    Base.metadata.drop_all(engine)
