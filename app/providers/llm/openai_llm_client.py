import logging
import time
from typing import TypeVar

from openai import BadRequestError, OpenAI
from pydantic import BaseModel

from app.constants.llm import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS, STRUCTURED_SAMPLING
from app.domain import ChatTurn, ToolCall
from app.errors import ProviderError, ProviderNotConfigured

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenAILLMClient:
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ProviderNotConfigured("OPENAI_API_KEY is not set")
        self.model = model
        self._client = OpenAI(api_key=api_key, max_retries=LLM_MAX_RETRIES, timeout=LLM_TIMEOUT_SECONDS)

    def structured(self, system_prompt: str, user_prompt: str, response_model: type[T]) -> T:
        started = time.perf_counter()
        request = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "response_format": response_model,
        }
        try:
            try:
                completion = self._client.chat.completions.parse(**request, **STRUCTURED_SAMPLING)
            except BadRequestError as exc:
                # Some models (reasoning models) reject sampling parameters. Fall back to the model's defaults.
                if not any(name in str(exc) for name in STRUCTURED_SAMPLING):
                    raise
                logger.info("%s rejected sampling parameters; retrying with defaults", self.model)
                completion = self._client.chat.completions.parse(**request)
        except Exception as exc:
            raise ProviderError(f"OpenAI call failed: {exc}") from exc

        message = completion.choices[0].message
        if message.parsed is None:
            raise ProviderError(f"OpenAI returned no parsable output (refusal: {message.refusal})")
        usage = completion.usage
        logger.info(
            "openai %s -> %s: %s in / %s out tokens, %.2fs",
            self.model,
            response_model.__name__,
            getattr(usage, "prompt_tokens", "?"),
            getattr(usage, "completion_tokens", "?"),
            time.perf_counter() - started,
        )
        return message.parsed

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatTurn:
        started = time.perf_counter()
        try:
            completion = self._client.chat.completions.create(
                model=self.model, messages=messages, **({"tools": tools} if tools else {})
            )
        except Exception as exc:
            raise ProviderError(f"OpenAI call failed: {exc}") from exc

        message = completion.choices[0].message
        calls = [ToolCall(c.id, c.function.name, c.function.arguments) for c in (message.tool_calls or [])]
        usage = completion.usage
        logger.info(
            "openai %s chat: %d tool calls, %s in / %s out tokens, %.2fs",
            self.model,
            len(calls),
            getattr(usage, "prompt_tokens", "?"),
            getattr(usage, "completion_tokens", "?"),
            time.perf_counter() - started,
        )
        return ChatTurn(content=message.content, tool_calls=calls)
