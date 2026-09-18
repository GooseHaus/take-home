from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.constants.market import MARKET_TICKER
from app.domain import Peer, Profile
from app.enums import DriverHint, ExplanationCategory
from app.errors import ProviderError
from app.main import app
from app.models import Company, Movement, Price
from app.repositories.prices import upsert_prices
from app.schemas.llm import ExplanationOutput, PeersOutput, PeerSuggestion
from app.services.explain import NO_PEER_MOVES, build_user_prompt
from app.services.movements import detect_movements, driver_hint, peer_median
from app.services.peers import company_peers, ensure_peers, ingest_peer_prices, load_peer_returns, peer_moves_on
from tests.factories import price_frame
from tests.fakes.fake_llm_client import FakeLLMClient
from tests.fakes.fake_market_data_provider import FakeMarketDataProvider
from tests.fakes.fake_news_provider import FakeNewsProvider
from tests.pipeline_helpers import CLOSES, ingest
from tests.seed import DOWN_DAY, UP_DAY, seed_ticker

START, END = date(2026, 1, 5), date(2026, 1, 31)


def suggest(*peers: tuple[str, str | None]):
    def reply(user_prompt, response_model):
        return PeersOutput(peers=[PeerSuggestion(name=name, ticker=ticker) for name, ticker in peers])

    return reply


def acme(session, peers=None) -> Company:
    company = Company(ticker="ACME", name="Acme Corp", industry="Widgets", peers=peers)
    session.add(company)
    session.flush()
    return company


# --- who the peers are -----------------------------------------------------------------------------------------------


def test_suggested_peers_are_stored_with_cleaned_tickers(session):
    llm = FakeLLMClient(
        suggest(("Globex", " glbx "), ("Initech", None), ("Acme Corp", "ACME"), ("Odd", "not a ticker"))
    )
    peers = ensure_peers(session, llm, acme(session))
    assert peers == [Peer("Globex", "GLBX"), Peer("Initech"), Peer("Acme Corp"), Peer("Odd")]  # own ticker dropped


def test_peers_stored_as_plain_names_are_upgraded_once(session):
    company = acme(session, peers=["Globex", "Initech"])  # the format written before tickers were supported
    assert company_peers(company) == [Peer("Globex"), Peer("Initech")]

    llm = FakeLLMClient(suggest(("Globex", "GLBX")))
    assert ensure_peers(session, llm, company) == [Peer("Globex", "GLBX")]
    ensure_peers(session, llm, company)
    assert len(llm.calls) == 1


def test_failed_suggestion_keeps_whatever_was_stored(session):
    def fail(user_prompt, response_model):
        raise ProviderError("rate limited")

    company = acme(session, peers=["Globex"])
    assert ensure_peers(session, FakeLLMClient(fail), company) == [Peer("Globex")]
    assert company.peers == ["Globex"]


# --- their prices ----------------------------------------------------------------------------------------------------


def test_peer_prices_are_fetched_only_for_peers_with_a_ticker_and_failures_are_skipped(session):
    provider = FakeMarketDataProvider({"GLBX": price_frame([50, 51])})
    peers = [Peer("Globex", "GLBX"), Peer("Initech"), Peer("Delisted Co", "GONE")]
    assert ingest_peer_prices(session, provider, peers, START, END) == ["GLBX"]
    assert {t for (t,) in session.query(Price.ticker).distinct()} == {"GLBX"}
    assert [t for t, *_ in provider.history_calls] == ["GLBX", "GONE"]


def test_peer_moves_on_a_day(session):
    upsert_prices(session, "GLBX", price_frame([50, 50, 50, 48.5]))
    peers = [Peer("Globex", "GLBX"), Peer("Initech"), Peer("No Prices", "NOPX")]
    returns = load_peer_returns(session, peers)
    (move,) = peer_moves_on(DOWN_DAY, peers, returns)
    assert (move.name, move.ticker, move.pct_change) == ("Globex", "GLBX", -3.0)
    assert peer_moves_on(date(2026, 1, 4), peers, returns) == []  # a day with no bar


# --- the driver hint -------------------------------------------------------------------------------------------------


def returns(*values: float) -> dict[str, pd.Series]:
    return {f"P{i}": pd.Series([v], index=[DOWN_DAY]) for i, v in enumerate(values)}


def test_peer_median_needs_at_least_two_peers():
    assert peer_median(DOWN_DAY, returns(-4.0)) is None
    assert peer_median(DOWN_DAY, returns(-4.0, -2.0, -3.0)) == -3.0
    assert peer_median(DOWN_DAY, None) is None


@pytest.mark.parametrize(
    "pct, market, sector, peers, expected",
    [
        (-5.0, -0.2, -0.3, -4.0, DriverHint.SECTOR),  # competitors fell together; the broad sector ETF did not
        (-5.0, -0.2, -0.3, 0.5, DriverHint.IDIOSYNCRATIC),  # fell alone
        (-5.0, -0.2, -0.3, None, DriverHint.IDIOSYNCRATIC),
        (-5.0, -3.0, -0.3, -4.0, DriverHint.MARKET),  # the market still comes first
    ],
)
def test_peers_moving_together_count_as_a_sector_move(pct, market, sector, peers, expected):
    assert driver_hint(pct, market, sector, peers) is expected


def test_detection_uses_peer_returns_for_the_hint():
    prices, flat = price_frame([100, 95]), price_frame([100, 100])
    day = prices.index[1]
    together = {t: pd.Series([-4.0], index=[day]) for t in ("P1", "P2")}
    (alone,) = detect_movements(prices, flat, flat, 2.0)
    (with_peers,) = detect_movements(prices, flat, flat, 2.0, peer_returns=together)
    assert (alone.driver_hint, with_peers.driver_hint) == (DriverHint.IDIOSYNCRATIC, DriverHint.SECTOR)


# --- what the model and the API see ----------------------------------------------------------------------------------


def test_explanation_prompt_lists_competitor_moves(session):
    seed_ticker(session)
    company = session.get(Company, "ACME")
    movement = session.query(Movement).filter_by(ticker="ACME", date=DOWN_DAY).one()
    peers = company_peers(company)
    prompt = build_user_prompt(movement, company, [], peer_moves_on(DOWN_DAY, peers, load_peer_returns(session, peers)))
    assert "## Same-day moves of its closest competitors\nGlobex (GLBX): -3.00%" in prompt
    assert NO_PEER_MOVES in build_user_prompt(movement, company, [])


def test_pipeline_fetches_peer_prices_and_shows_them_to_the_model(session):
    def reply(user_prompt, response_model):
        if response_model is PeersOutput:
            return PeersOutput(peers=[PeerSuggestion(name="Globex", ticker="GLBX")])
        return ExplanationOutput(
            summary="ok", category=ExplanationCategory.COMPANY, confidence=0.8, article_relevance=[]
        )

    frames = {
        "ACME": price_frame(CLOSES),
        MARKET_TICKER: price_frame([400] * len(CLOSES)),
        "GLBX": price_frame([50, 50.5, 50.5, 50.5, 50.5, 50.5, 50.5]),
    }
    data = FakeMarketDataProvider(frames, {"ACME": Profile("ACME", "Acme Corp", None, "Widgets", None)})
    llm = FakeLLMClient(reply)
    job = ingest(session, FakeNewsProvider(), llm, data=data)
    assert job.detail["peer_prices"] == ["GLBX"]
    prompts = [user for _, user, model in llm.calls if model is ExplanationOutput]
    assert any("Date: 2026-01-06" in p and "Globex (GLBX): +1.00%" in p for p in prompts)


def test_api_returns_peers_and_peer_moves(session):
    seed_ticker(session)
    with TestClient(app) as client:
        data = client.get("/tickers/ACME?sort=date_asc&include_prices=false").json()
    assert data["summary"]["company"]["peers"] == [
        {"name": "Globex", "ticker": "GLBX"},
        {"name": "Initech", "ticker": None},
    ]
    by_date = {m["date"]: m["peer_moves"] for m in data["movements"]}
    assert by_date[str(UP_DAY)] == [{"name": "Globex", "ticker": "GLBX", "pct_change": 0.0}]
    assert by_date[str(DOWN_DAY)] == [{"name": "Globex", "ticker": "GLBX", "pct_change": -3.0}]
