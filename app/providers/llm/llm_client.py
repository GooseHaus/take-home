from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    model: str

    def structured(self, system_prompt: str, user_prompt: str, response_model: type[T]) -> T:
        """One completion parsed into `response_model`. Raises ProviderError on failure or refusal."""
        ...
