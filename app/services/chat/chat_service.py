"""The chat loop (D8): model -> tool calls -> tool results -> model, grounded in the same read layer as the REST API."""

import json
import logging
import re
import uuid
from datetime import date

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import Settings
from app.constants.chat import HISTORY_MESSAGES, MAX_TOOL_ROUNDS
from app.domain import ToolCall
from app.errors import AppError, ConversationNotFound
from app.prompts import load_prompt
from app.providers.llm import LLMClient
from app.repositories import chat_messages, movement_queries
from app.schemas.chat import ChatMessageResponse, ChatRequest, ChatResponse, Citation, ToolCallTrace
from app.services import ticker_data
from app.services.chat.tool_schema import tool_specs
from app.services.chat.tools.chat_tool import ChatTool
from app.services.chat.tools.registry import CHAT_TOOLS

logger = logging.getLogger(__name__)

NO_TICKERS = "(none yet)"
OUT_OF_ROUNDS = "You have used all your tool calls. Answer now using only what the tools have already returned."
URL_END = r"(?![A-Za-z0-9\-._~%/?#=&+])"
EMPTY_ANSWER = "I couldn't produce an answer from the stored data."


def build_system_prompt(session: Session, settings: Settings, focus_ticker: str | None, today: date) -> str:
    tickers = ", ".join(f"{c.ticker} ({c.name})" for c in movement_queries.list_companies(session))
    focus = f"The user is currently looking at {focus_ticker}; assume questions are about it unless they say otherwise."
    return load_prompt("chat_system").substitute(
        today=f"{today.isoformat()} ({today.strftime('%A')})",
        threshold_pct=f"{settings.move_threshold_pct:g}",
        tickers=tickers or NO_TICKERS,
        focus=focus if focus_ticker else "",
    )


def replayable_history(session: Session, conversation_id: str) -> list[dict]:
    """Earlier user questions and final assistant answers only.

    Tool calls and results are stored but not replayed: it keeps follow-up turns cheap and means truncation can
    never orphan a tool result from its call. The model re-queries when it needs the detail again.
    """
    turns = [
        {"role": m.role, "content": m.content["content"]}
        for m in chat_messages.get_messages(session, conversation_id)
        if m.role == "user" or (m.role == "assistant" and not m.content.get("tool_calls"))
    ]
    return turns[-HISTORY_MESSAGES:]


def run_tool(session: Session, tools: dict[str, ChatTool], call: ToolCall) -> tuple[dict, dict]:
    """(parsed arguments, result). Every failure becomes an `error` result the model can read and recover from."""
    tool = tools.get(call.name)
    if tool is None:
        return {}, {"error": f"Unknown tool '{call.name}'"}
    try:
        args = tool.args_model.model_validate_json(call.arguments or "{}")
    except ValidationError as exc:
        return {}, {"error": f"Invalid arguments: {exc.errors(include_url=False, include_input=False)}"}
    # The trace shows what the model asked for, not every default the args model filled in
    supplied = args.model_dump(mode="json", exclude_unset=True)
    try:
        return supplied, tool.run(session, args)
    except AppError as exc:
        return supplied, {"error": exc.message}
    except Exception:
        # By now the turn has paid for at least one LLM call. Report the failure to the model instead of a 500.
        logger.exception("chat tool %s crashed", call.name)
        return supplied, {"error": "The tool failed unexpectedly."}


def collect_articles(node, found: dict[str, Citation]) -> None:
    """Every {title, url} pair anywhere in a tool result: the only URLs an answer is allowed to cite."""
    if isinstance(node, list):
        for item in node:
            collect_articles(item, found)
    elif isinstance(node, dict):
        if isinstance(node.get("url"), str) and node.get("title"):
            found.setdefault(node["url"], Citation(title=node["title"], url=node["url"], source=node.get("source")))
        for value in node.values():
            collect_articles(value, found)


def citations_in(answer: str, seen: dict[str, Citation]) -> list[Citation]:
    """Articles the answer actually links to, in order of appearance. URLs the tools never returned are ignored."""
    cited = []
    for url, citation in seen.items():
        # The URL must end where it ends in the answer, so ".../a" is not counted as cited by a link to ".../a-b"
        match = re.search(re.escape(url) + URL_END, answer)
        if match:
            cited.append((match.start(), citation))
    return [citation for _, citation in sorted(cited, key=lambda pair: pair[0])]


def chat(
    session: Session,
    llm: LLMClient,
    settings: Settings,
    request: ChatRequest,
    tools: list[ChatTool] | None = None,
    today: date | None = None,
) -> ChatResponse:
    tools = CHAT_TOOLS if tools is None else tools
    by_name = {tool.name: tool for tool in tools}
    specs = tool_specs(tools)

    conversation_id = request.conversation_id or uuid.uuid4().hex
    if request.conversation_id and not chat_messages.conversation_exists(session, conversation_id):
        raise ConversationNotFound(f"No conversation '{conversation_id}'")
    focus = ticker_data.normalize_ticker(request.ticker) if request.ticker else None

    system = {"role": "system", "content": build_system_prompt(session, settings, focus, today or date.today())}
    new_messages: list[dict] = [{"role": "user", "content": request.message}]
    context = [system, *replayable_history(session, conversation_id)]

    seen_articles: dict[str, Citation] = {}
    trace: list[ToolCallTrace] = []
    answer = None
    for _ in range(MAX_TOOL_ROUNDS):
        turn = llm.chat(context + new_messages, specs)
        new_messages.append(turn.as_message())
        if not turn.tool_calls:
            answer = turn.content
            break
        for call in turn.tool_calls:
            arguments, result = run_tool(session, by_name, call)
            trace.append(ToolCallTrace(name=call.name, arguments=arguments))
            collect_articles(result, seen_articles)
            new_messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, default=str)})
    else:
        logger.warning("chat %s hit the tool-round limit", conversation_id)
        final = llm.chat(context + new_messages + [{"role": "user", "content": OUT_OF_ROUNDS}], None)
        new_messages.append(final.as_message())
        answer = final.content

    answer = (answer or EMPTY_ANSWER).strip()
    new_messages[-1]["content"] = answer
    chat_messages.add_messages(session, conversation_id, new_messages)
    session.commit()
    return ChatResponse(
        conversation_id=conversation_id,
        answer=answer,
        citations=citations_in(answer, seen_articles),
        tool_calls=trace,
    )


def get_conversation(session: Session, conversation_id: str) -> list[ChatMessageResponse]:
    messages = chat_messages.get_messages(session, conversation_id)
    if not messages:
        raise ConversationNotFound(f"No conversation '{conversation_id}'")
    return [
        ChatMessageResponse(role=m.role, content=m.content["content"], created_at=m.created_at)
        for m in messages
        if m.role == "user" or (m.role == "assistant" and not m.content.get("tool_calls"))
    ]
