from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.domain import ChatTurn

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    model: str

    def structured(self, system_prompt: str, user_prompt: str, response_model: type[T]) -> T:
        """One completion parsed into `response_model`. Raises ProviderError on failure or refusal."""
        ...

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatTurn:
        """One assistant turn over chat-completions-style messages, optionally offering function tools.

        Raises ProviderError on failure.
        """
        ...
