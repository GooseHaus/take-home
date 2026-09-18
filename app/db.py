from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.constants.pipeline import SQLITE_BUSY_TIMEOUT_SECONDS


class Base(DeclarativeBase):
    pass


def make_engine(url: str, busy_timeout_seconds: float = SQLITE_BUSY_TIMEOUT_SECONDS):
    # check_same_thread=False: background ingest tasks use their own sessions on other threads
    connect_args = {"check_same_thread": False, "timeout": busy_timeout_seconds}
    if ":memory:" in url:
        # One shared connection, otherwise every session sees its own empty in-memory DB
        return create_engine(url, connect_args=connect_args, poolclass=StaticPool)
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args=connect_args)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _use_wal)
    return engine


def _use_wal(dbapi_connection, _record) -> None:
    """Write-ahead logging lets requests read while an ingest is writing. SQLite still allows one writer at a time,
    so the pipeline keeps its write transactions short and never holds one across a network call."""
    dbapi_connection.execute("PRAGMA journal_mode=WAL")


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    from app import models  # noqa: F401  (registers tables on Base.metadata)

    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
