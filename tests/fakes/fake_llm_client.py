from collections.abc import Callable

from pydantic import BaseModel

from app.domain import ChatTurn


class FakeLLMClient:
    """LLMClient for tests. Records every call.

    `reply(user_prompt, response_model)` answers structured requests; `turns` is the scripted sequence of chat
    replies (each either a ChatTurn or a callable taking the messages sent, for replies that depend on tool output).
    """

    model = "fake-model"

    def __init__(
        self,
        reply: Callable[[str, type[BaseModel]], BaseModel] | None = None,
        turns: list[ChatTurn | Callable[[list[dict]], ChatTurn]] | None = None,
    ):
        self._reply = reply
        self._turns = list(turns or [])
        self.calls: list[tuple[str, str, type[BaseModel]]] = []
        self.chat_calls: list[tuple[list[dict], list[dict] | None]] = []

    def structured(self, system_prompt: str, user_prompt: str, response_model: type[BaseModel]) -> BaseModel:
        self.calls.append((system_prompt, user_prompt, response_model))
        return self._reply(user_prompt, response_model)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatTurn:
        self.chat_calls.append(([dict(m) for m in messages], tools))
        turn = self._turns.pop(0)
        return turn(messages) if callable(turn) else turn
