import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.constants.chat import MAX_TOOL_ROUNDS
from app.dependencies import get_llm_client
from app.domain import ChatTurn, ToolCall
from app.main import app
from app.models import ChatMessage
from app.schemas.chat import ListMovementsArgs
from app.schemas.movement_filters import MovementFilters
from app.services.chat.tool_schema import tool_specs
from app.services.chat.tools.registry import CHAT_TOOLS
from tests.fakes.fake_llm_client import FakeLLMClient
from tests.seed import DOWN_DAY, UP_DAY, seed_ticker

EARNINGS_URL = "https://news.example.com/acme-earnings"
FED_URL = "https://news.example.com/fed-hike"


def call(name: str, **arguments) -> ChatTurn:
    return ChatTurn(content=None, tool_calls=[ToolCall(f"call_{name}", name, json.dumps(arguments, default=str))])


def say(text: str) -> ChatTurn:
    return ChatTurn(content=text)


def tool_results(messages: list[dict]) -> list[dict]:
    return [json.loads(m["content"]) for m in messages if m["role"] == "tool"]


@pytest.fixture
def ask(session):
    """ask(turns, message, **request_fields) -> (response, fake_llm). Seeds ACME and scripts the model's replies."""
    seed_ticker(session)

    def _ask(turns, message="Why did Acme jump?", **fields):
        llm = FakeLLMClient(turns=turns)
        app.dependency_overrides[get_llm_client] = lambda: llm
        with TestClient(app) as client:
            return client.post("/chat", json={"message": message, **fields}), llm

    yield _ask
    app.dependency_overrides.clear()


# --- tool schemas ----------------------------------------------------------------------------------------------------


def test_tool_schemas_are_generated_from_the_shared_filter_model():
    specs = {s["function"]["name"]: s["function"] for s in tool_specs(CHAT_TOOLS)}
    assert set(specs) == {"list_tickers", "list_movements", "get_movement", "search_articles", "price_summary"}

    properties = specs["list_movements"]["parameters"]["properties"]
    assert set(properties) == set(MovementFilters.model_fields) | {"ticker"}
    assert set(ListMovementsArgs.model_fields) == set(properties)
    assert specs["list_movements"]["parameters"]["required"] == ["ticker"]
    assert properties["category"]["anyOf"][0]["enum"] == ["company", "industry", "macro", "unexplained"]
    assert "$ref" not in json.dumps(specs) and specs["list_tickers"]["parameters"]["properties"] == {}


# --- the loop --------------------------------------------------------------------------------------------------------


def test_answer_is_grounded_in_tool_results_and_cites_only_linked_articles(ask):
    def answer_from_results(messages):
        (result,) = tool_results(messages)
        movement = result["movements"][0]
        return say(f"Acme rose {movement['pct_change']}% on {movement['date']}: [earnings beat]({EARNINGS_URL}).")

    response, llm = ask([call("list_movements", ticker="ACME", direction="up", sort="magnitude"), answer_from_results])
    body = response.json()

    assert response.status_code == 200
    assert body["answer"] == f"Acme rose 5.0% on {UP_DAY}: [earnings beat]({EARNINGS_URL})."
    assert body["citations"] == [{"title": "Acme Earnings", "url": EARNINGS_URL, "source": "news.example.com"}]
    assert body["tool_calls"] == [
        {"name": "list_movements", "arguments": {"ticker": "ACME", "direction": "up", "sort": "magnitude",
                                                 "explained_only": False, "limit": 10, "offset": 0}}
    ]  # fmt: skip

    first_messages, first_tools = llm.chat_calls[0]
    assert first_messages[0]["role"] == "system" and "ACME (Acme Corp)" in first_messages[0]["content"]
    assert len(first_tools) == len(CHAT_TOOLS)


def test_urls_the_tools_never_returned_are_not_cited(ask):
    response, _ = ask([call("list_movements", ticker="ACME"), say("See [this](https://made-up.example.com/story).")])
    assert response.json()["citations"] == []


def test_each_tool_runs_against_the_seeded_data(ask):
    captured = {}

    def capture(messages):
        captured["results"] = tool_results(messages)
        return say("done")

    turns = [
        ChatTurn(
            content=None,
            tool_calls=[
                ToolCall("1", "list_tickers", "{}"),
                ToolCall("2", "get_movement", json.dumps({"ticker": "acme", "date": str(DOWN_DAY)})),
                ToolCall("3", "search_articles", json.dumps({"query": "fed"})),
                ToolCall("4", "price_summary", json.dumps({"ticker": "ACME"})),
            ],
        ),
        capture,
    ]
    ask(turns)
    tickers, movement, search, prices = captured["results"]

    assert tickers["tickers"][0]["company"]["ticker"] == "ACME" and tickers["tickers"][0]["explained_count"] == 2
    assert movement["category"] == "macro" and movement["articles"][0]["excerpt"] == "Snippet for fed-hike."
    assert [a["url"] for a in search["articles"]] == [FED_URL]
    assert search["articles"][0]["linked_movements"] == [{"ticker": "ACME", "date": str(DOWN_DAY), "pct_change": -4.0}]
    assert (prices["start_close"], prices["end_close"], prices["total_return_pct"]) == (100, 103.82, 3.82)
    assert prices["major_movements"] == 3


def test_tool_failures_are_reported_to_the_model_not_raised(ask):
    captured = {}

    def capture(messages):
        captured["results"] = tool_results(messages)
        return say("TSLA hasn't been ingested.")

    turns = [
        ChatTurn(
            content=None,
            tool_calls=[
                ToolCall("1", "list_movements", json.dumps({"ticker": "TSLA"})),
                ToolCall("2", "list_movements", json.dumps({"ticker": "ACME", "direction": "sideways"})),
                ToolCall("3", "no_such_tool", "{}"),
                ToolCall("4", "get_movement", "not json"),
            ],
        ),
        capture,
    ]
    response, _ = ask(turns)
    not_ingested, bad_args, unknown, bad_json = captured["results"]

    assert response.status_code == 200
    assert "POST /tickers/TSLA/ingest" in not_ingested["error"]
    assert "Invalid arguments" in bad_args["error"] and "Invalid arguments" in bad_json["error"]
    assert unknown["error"] == "Unknown tool 'no_such_tool'"


def test_round_limit_forces_a_final_answer_without_tools(ask):
    turns = [call("list_tickers")] * MAX_TOOL_ROUNDS + [say("Best answer I have.")]
    response, llm = ask(turns)
    assert response.json()["answer"] == "Best answer I have."
    assert len(llm.chat_calls) == MAX_TOOL_ROUNDS + 1
    final_messages, final_tools = llm.chat_calls[-1]
    assert final_tools is None and final_messages[-1]["role"] == "system"


def test_focus_ticker_and_today_reach_the_system_prompt(ask):
    _, llm = ask([say("ok")], ticker="acme")
    system = llm.chat_calls[0][0][0]["content"]
    assert "The user is currently looking at ACME" in system and date.today().isoformat() in system


# --- conversations ---------------------------------------------------------------------------------------------------


def test_follow_up_replays_questions_and_answers_but_not_tool_traffic(ask, session):
    first, _ = ask([call("list_movements", ticker="ACME"), say("It jumped 5% on earnings.")])
    conversation_id = first.json()["conversation_id"]

    second, llm = ask(
        [say("No, that one was company-specific.")], "Was that the market?", conversation_id=conversation_id
    )
    assert second.json()["conversation_id"] == conversation_id

    sent = llm.chat_calls[0][0]
    assert [(m["role"], m["content"]) for m in sent[1:]] == [
        ("user", "Why did Acme jump?"),
        ("assistant", "It jumped 5% on earnings."),
        ("user", "Was that the market?"),
    ]
    stored_roles = [m.role for m in session.query(ChatMessage).order_by(ChatMessage.id)]
    assert stored_roles == ["user", "assistant", "tool", "assistant", "user", "assistant"]  # full audit trail kept


def test_conversation_history_endpoint(ask):
    first, _ = ask([call("list_movements", ticker="ACME"), say("It jumped 5% on earnings.")])
    conversation_id = first.json()["conversation_id"]
    with TestClient(app) as client:
        history = client.get(f"/chat/{conversation_id}").json()
        missing = client.get("/chat/nope")
    assert [(m["role"], m["content"]) for m in history] == [
        ("user", "Why did Acme jump?"),
        ("assistant", "It jumped 5% on earnings."),
    ]
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "conversation_not_found"


def test_unknown_conversation_id_is_rejected(ask):
    response, llm = ask([say("unused")], conversation_id="does-not-exist")
    assert response.status_code == 404 and llm.chat_calls == []


@pytest.mark.parametrize("body", [{"message": ""}, {}, {"message": "x" * 5000}])
def test_bad_chat_requests(ask, body):
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient()
    with TestClient(app) as client:
        assert client.post("/chat", json=body).status_code == 422


def test_chat_without_an_api_key_is_a_503_naming_the_key(ask):
    get_llm_client.cache_clear()
    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 503
    assert response.json()["error"] == {"code": "provider_not_configured", "message": "OPENAI_API_KEY is not set"}
