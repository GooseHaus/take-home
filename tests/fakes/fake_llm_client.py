from collections.abc import Callable

from pydantic import BaseModel


class FakeLLMClient:
    """LLMClient whose replies come from a callable `(user_prompt, response_model) -> BaseModel`. Records prompts."""

    model = "fake-model"

    def __init__(self, reply: Callable[[str, type[BaseModel]], BaseModel]):
        self._reply = reply
        self.calls: list[tuple[str, str, type[BaseModel]]] = []

    def structured(self, system_prompt: str, user_prompt: str, response_model: type[BaseModel]) -> BaseModel:
        self.calls.append((system_prompt, user_prompt, response_model))
        return self._reply(user_prompt, response_model)
