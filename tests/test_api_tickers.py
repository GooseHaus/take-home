import pytest
from fastapi.testclient import TestClient

from app.constants.market import MARKET_TICKER
from app.dependencies import get_llm_client, get_market_data_provider, get_news_provider
from app.domain import Profile
from app.enums import ExplanationCategory
from app.errors import ProviderNotConfigured
from app.main import app
from app.repositories.ingest_jobs import create_job
from app.schemas.llm import ExplanationOutput, PeersOutput, PeerSuggestion
from tests.factories import article_hit, price_frame
from tests.fakes.fake_llm_client import FakeLLMClient
from tests.fakes.fake_market_data_provider import FakeMarketDataProvider
from tests.fakes.fake_news_provider import FakeNewsProvider
from tests.seed import CLOSES, DOWN_DAY, UNEXPLAINED_DAY, UP_DAY, seed_ticker


def llm_reply(user_prompt, response_model):
    if response_model is PeersOutput:
        return PeersOutput(peers=[PeerSuggestion(name="Globex", ticker="GLBX")])
    return ExplanationOutput(
        summary="Explained.", category=ExplanationCategory.COMPANY, confidence=0.8, article_relevance=[]
    )


@pytest.fixture
def client(session):
    frames = {"ACME": price_frame(CLOSES), MARKET_TICKER: price_frame([400] * len(CLOSES))}
    app.dependency_overrides[get_market_data_provider] = lambda: FakeMarketDataProvider(
        frames, {"ACME": Profile("ACME", "Acme Corp", None, "Widgets", None)}
    )
    app.dependency_overrides[get_news_provider] = lambda: FakeNewsProvider([article_hit("acme-earnings")])
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient(llm_reply)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seeded(client, session):
    seed_ticker(session)
    return client


def dates(response) -> list[str]:
    return [m["date"] for m in response.json()["movements"]]


# --- ingest + status -------------------------------------------------------------------------------------------------


def test_ingest_runs_in_the_background_and_status_reports_it(client):
    accepted = client.post("/tickers/acme/ingest", json={"start": "2026-01-05", "end": "2026-01-31"})
    assert accepted.status_code == 202
    assert accepted.json()["ticker"] == "ACME" and accepted.json()["status"] == "pending"
    assert accepted.json()["detail"]["params"]["threshold_pct"] == 2.0

    status = client.get("/tickers/ACME/status").json()  # TestClient runs background tasks before returning
    assert (status["status"], status["stage"]) == ("done", "complete")
    assert status["detail"]["movements"] == 3 and status["detail"]["explained"] == 3

    data = client.get("/tickers/ACME").json()
    assert data["summary"]["explained_count"] == 3 and data["latest_ingest"]["id"] == status["id"]


def test_ingest_with_no_body_uses_defaults(client):
    params = client.post("/tickers/ACME/ingest").json()["detail"]["params"]
    assert params["max_movements"] == 25 and params["refresh"] is False


def test_ingest_already_in_flight_is_returned_not_duplicated(client, session):
    running = create_job(session, "ACME", {})
    session.commit()
    response = client.post("/tickers/ACME/ingest")
    assert response.status_code == 200 and response.json()["id"] == running.id


def test_unknown_ticker_surfaces_on_the_job(client):
    client.post("/tickers/NOPE/ingest")
    status = client.get("/tickers/NOPE/status").json()
    assert status["status"] == "failed" and "No price data" in status["error"]


@pytest.mark.parametrize(
    "body",
    [
        {"start": "2026-02-01", "end": "2026-01-01"},
        {"start": "2026-01-01", "lookback_days": 30},
        {"threshold_pct": 0},
        {"lookback_days": 100000},
    ],
)
def test_bad_ingest_requests_are_rejected(client, body):
    assert client.post("/tickers/ACME/ingest", json=body).status_code == 422


def test_missing_api_key_is_a_503_before_any_job_exists(client):
    def unconfigured():
        raise ProviderNotConfigured("EXA_API_KEY is not set")

    app.dependency_overrides[get_news_provider] = unconfigured
    response = client.post("/tickers/ACME/ingest")
    assert response.status_code == 503 and response.json()["error"]["code"] == "provider_not_configured"
    assert client.get("/tickers/ACME/status").status_code == 404


def test_status_for_a_ticker_never_requested(client):
    response = client.get("/tickers/ACME/status")
    assert response.status_code == 404 and response.json()["error"]["code"] == "ticker_not_ingested"


# --- ticker data + filters -------------------------------------------------------------------------------------------


def test_everything_for_a_ticker(seeded):
    data = seeded.get("/tickers/ACME").json()
    assert data["summary"]["company"]["name"] == "Acme Corp"
    assert (data["summary"]["movement_count"], data["summary"]["explained_count"]) == (3, 2)
    assert data["total_movements"] == 3 and len(data["prices"]) == len(CLOSES)
    assert dates(seeded.get("/tickers/ACME")) == [str(UNEXPLAINED_DAY), str(DOWN_DAY), str(UP_DAY)]

    up = data["movements"][-1]
    assert up["explanation"]["category"] == "company" and up["driver_hint"] == "idiosyncratic"
    assert [(a["title"], a["cited"]) for a in up["articles"]] == [("Acme Earnings", True), ("Acme Store", False)]
    assert data["movements"][0]["explanation"] is None


@pytest.mark.parametrize(
    "query, expected",
    [
        ("direction=up", [UNEXPLAINED_DAY, UP_DAY]),
        ("direction=down", [DOWN_DAY]),
        ("min_abs_change=4", [DOWN_DAY, UP_DAY]),
        ("category=macro", [DOWN_DAY]),
        ("driver_hint=sector", [UNEXPLAINED_DAY]),
        ("min_confidence=0.8", [UP_DAY]),
        ("explained_only=true", [DOWN_DAY, UP_DAY]),
        ("start=2026-01-07&end=2026-01-09", [DOWN_DAY]),
        ("sort=date_asc", [UP_DAY, DOWN_DAY, UNEXPLAINED_DAY]),
        ("sort=magnitude", [UP_DAY, DOWN_DAY, UNEXPLAINED_DAY]),
        ("direction=up&category=company", [UP_DAY]),
        ("category=industry", []),
    ],
)
def test_movement_filters(seeded, query, expected):
    assert dates(seeded.get(f"/tickers/ACME?{query}")) == [str(d) for d in expected]


def test_pagination_reports_the_unpaged_total(seeded):
    page = seeded.get("/tickers/ACME?sort=date_asc&limit=1&offset=1")
    assert dates(page) == [str(DOWN_DAY)] and page.json()["total_movements"] == 3


def test_article_filters_narrow_articles_not_movements(seeded):
    cited_only = seeded.get("/tickers/ACME?min_relevance=0.5&sort=date_asc").json()
    assert cited_only["total_movements"] == 3
    assert [len(m["articles"]) for m in cited_only["movements"]] == [1, 1, 0]

    macro_only = seeded.get("/tickers/ACME?tier=macro&sort=date_asc").json()
    assert [len(m["articles"]) for m in macro_only["movements"]] == [0, 1, 0]


def test_prices_follow_the_date_filter_and_can_be_left_out(seeded):
    windowed = seeded.get("/tickers/ACME?start=2026-01-07&end=2026-01-09").json()
    assert [p["date"] for p in windowed["prices"]] == ["2026-01-07", "2026-01-08", "2026-01-09"]

    slim = seeded.get("/tickers/ACME?include_prices=false&include_news=false").json()
    assert slim["prices"] is None and all(m["articles"] == [] for m in slim["movements"])
    assert slim["movements"][-1]["explanation"] is not None  # explanations stay; only the article lists go


@pytest.mark.parametrize(
    "query", ["direction=sideways", "min_confidence=2", "limit=0", "limit=1000", "start=2026-02-01&end=2026-01-01"]
)
def test_bad_filters_are_rejected(seeded, query):
    assert seeded.get(f"/tickers/ACME?{query}").status_code == 422


def test_ticker_not_ingested_points_at_the_ingest_endpoint(client):
    response = client.get("/tickers/msft")
    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "ticker_not_ingested",
        "message": "No data for MSFT yet. POST /tickers/MSFT/ingest first.",
    }


def test_malformed_ticker(client):
    response = client.get("/tickers/not a ticker!")
    assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_ticker"


# --- single movement + listing ---------------------------------------------------------------------------------------


def test_single_movement(seeded):
    movement = seeded.get(f"/tickers/ACME/movements/{DOWN_DAY}").json()
    assert movement["pct_change"] == -4.0 and movement["explanation"]["category"] == "macro"
    assert [a["tier"] for a in movement["articles"]] == ["macro"]


def test_day_without_a_major_movement(seeded):
    response = seeded.get("/tickers/ACME/movements/2026-01-07")
    assert response.status_code == 404 and response.json()["error"]["code"] == "movement_not_found"


def test_list_tickers(seeded):
    (summary,) = seeded.get("/tickers").json()
    assert summary["company"]["ticker"] == "ACME" and summary["movement_count"] == 3
    assert (summary["first_price_date"], summary["last_price_date"]) == ("2026-01-05", "2026-01-12")
