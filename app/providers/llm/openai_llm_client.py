import logging
import time
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from app.constants.llm import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS
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
        try:
            completion = self._client.chat.completions.parse(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                response_format=response_model,
            )
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
