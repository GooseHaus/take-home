from datetime import date, timedelta

import pytest

from app.constants.market import MARKET_TICKER, WARMUP_DAYS
from app.domain import Profile
from app.enums import DriverHint
from app.errors import TickerNotFound
from app.models import Company, Movement, Price
from app.repositories.prices import load_price_frame
from app.services.price_ingest import ingest_prices
from tests.factories import price_frame
from tests.fakes.fake_market_data_provider import FakeMarketDataProvider

START, END = date(2026, 1, 5), date(2026, 1, 9)
ACME = Profile("ACME", "Acme Corp", "Technology", "Widgets", "XLK")


def provider() -> FakeMarketDataProvider:
    frames = {t: price_frame([100, 101, 102]) for t in ("ACME", MARKET_TICKER, "XLK")}
    return FakeMarketDataProvider(frames, {"ACME": ACME})


def test_ingests_ticker_profile_and_both_benchmarks(session):
    company = ingest_prices(session, provider(), "ACME", START, END)
    session.commit()
    assert (company.name, company.sector_etf) == ("Acme Corp", "XLK")
    assert {t for (t,) in session.query(Price.ticker).distinct()} == {"ACME", MARKET_TICKER, "XLK"}


def test_fetch_includes_warmup_history(session):
    fake = provider()
    ingest_prices(session, fake, "ACME", START, END)
    assert all(call_start == START - timedelta(days=WARMUP_DAYS) for _, call_start, _ in fake.history_calls)


def test_reingest_overwrites_instead_of_duplicating(session):
    ingest_prices(session, provider(), "ACME", START, END)
    restated = provider()
    restated.frames["ACME"] = price_frame([50, 50.5, 51])  # e.g. history re-adjusted after a split
    ingest_prices(session, restated, "ACME", START, END)
    session.commit()
    assert list(load_price_frame(session, "ACME")["close"]) == [50, 50.5, 51]


def test_unknown_ticker_writes_nothing(session):
    with pytest.raises(TickerNotFound):
        ingest_prices(session, provider(), "NOPE", START, END)
    assert session.query(Company).count() == 0 and session.query(Price).count() == 0


def test_no_sector_means_market_benchmark_only(session):
    fake = FakeMarketDataProvider({t: price_frame([1, 2]) for t in ("ETFX", MARKET_TICKER)})
    ingest_prices(session, fake, "ETFX", START, END)
    assert [t for t, _, _ in fake.history_calls] == ["ETFX", MARKET_TICKER]


def test_enum_columns_round_trip_as_enum_members(session):
    movement = Movement(
        ticker="ACME",
        date=START,
        close=105,
        prev_close=100,
        pct_change=5.0,
        driver_hint=DriverHint.SECTOR,
        window_start=START,
        window_end=END,
    )
    session.add(movement)
    session.commit()
    session.expire_all()
    assert session.query(Movement).one().driver_hint is DriverHint.SECTOR
    raw = session.connection().exec_driver_sql("select driver_hint from movements").scalar()
    assert raw == "sector"  # stored as the value, not the member name
