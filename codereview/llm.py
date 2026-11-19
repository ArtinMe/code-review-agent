"""Model access: a small interface, a Gemini implementation, and a cache.

Everything above this module talks to ``LLMClient``, so tests and the
evaluation harness can swap in a fake model.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

from .models import AgentOutput

T = TypeVar("T", bound=BaseModel)

RETRYABLE_CODES = {429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    model: str

    def review(self, system: str, prompt: str) -> AgentOutput: ...

    def generate(self, system: str, prompt: str, schema: type[T]) -> T: ...


class GeminiClient:
    """Calls Gemini with a JSON schema so every answer parses into a pydantic model."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_attempts: int = 4,
        base_delay: float = 2.0,
    ) -> None:
        from google import genai  # imported lazily so tests don't need the SDK configured
        from google.genai import types

        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY is not set.")
        # Structured JSON output is only served on the v1beta API surface.
        self._client = genai.Client(
            api_key=key, http_options=types.HttpOptions(api_version="v1beta")
        )
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.max_attempts = max_attempts
        self.base_delay = base_delay

    def review(self, system: str, prompt: str) -> AgentOutput:
        return self.generate(system, prompt, AgentOutput)

    def generate(self, system: str, prompt: str, schema: type[T]) -> T:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.2,
        )
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model, contents=prompt, config=config
                )
                return schema.model_validate_json(response.text or "{}")
            except errors.APIError as e:
                last_error = e
                if getattr(e, "code", None) not in RETRYABLE_CODES or attempt == self.max_attempts:
                    break
            except ValueError as e:  # malformed JSON despite the schema: retry once more
                last_error = e
                if attempt == self.max_attempts:
                    break
            time.sleep(backoff_seconds(last_error, attempt, self.base_delay))
        raise LLMError(describe_error(last_error)) from last_error


RATE_LIMIT_WAIT = 20.0  # free-tier quotas are per minute, so short waits just fail again


def backoff_seconds(error: Exception | None, attempt: int, base_delay: float) -> float:
    """Exponential backoff with jitter; rate limits wait long enough for the window to reset."""
    delay = base_delay * 2 ** (attempt - 1)
    if getattr(error, "code", None) == 429:
        delay = max(delay, RATE_LIMIT_WAIT * attempt)
    return delay + random.random()


def describe_error(error: Exception | None) -> str:
    code = getattr(error, "code", None)
    if code == 429:
        return "The model's rate limit was reached."
    if code in (500, 502, 503, 504):
        return "The model service is unavailable right now."
    if code in (401, 403):
        return "The model API key was rejected."
    if isinstance(error, ValueError):
        return "The model returned output that didn't match the schema."
    return "The model call failed."


class CachedClient:
    """Stores answers on disk keyed by model + prompt, so reruns cost nothing.

    Used by the CLI and the evaluation harness. Bump ``PROMPT_VERSION`` in
    ``agents.py`` to invalidate old answers after changing a prompt.
    """

    def __init__(self, inner: LLMClient, directory: str | Path = ".cache/llm") -> None:
        self.inner = inner
        self.model = inner.model
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, system: str, prompt: str) -> Path:
        digest = hashlib.sha256(f"{self.model}\n{system}\n{prompt}".encode()).hexdigest()
        return self.directory / f"{digest}.json"

    def review_with_meta(self, system: str, prompt: str) -> tuple[AgentOutput, bool]:
        """Return the answer and whether it came from the cache (safe across threads)."""
        path = self._path(system, prompt)
        if path.exists():
            return AgentOutput.model_validate_json(path.read_text()), True
        output = self.inner.review(system, prompt)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(output.model_dump(), indent=1))
        tmp.replace(path)  # atomic, so a crash never leaves a half-written answer
        return output, False

    def review(self, system: str, prompt: str) -> AgentOutput:
        return self.review_with_meta(system, prompt)[0]

    def generate(self, system: str, prompt: str, schema: type[T]) -> T:
        path = self._path(f"{schema.__name__}\n{system}", prompt)
        if path.exists():
            return schema.model_validate_json(path.read_text())
        output = self.inner.generate(system, prompt, schema)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(output.model_dump(), indent=1))
        tmp.replace(path)
        return output
