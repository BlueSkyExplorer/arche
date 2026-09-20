"""Provider boundary for schema-constrained LLM calls.

``StructuredLLMClient`` is the single seam the LLM extractor depends on. The
production adapter is ``app.services.ai_client.AIClient.complete_structured``
(OpenAI-compatible); ``FakeStructuredClient`` is the deterministic test adapter.
A future Anthropic/Gemini/local adapter implements the same protocol.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.services.ai_client import AIClient, StructuredLLMError

__all__ = ["AIClient", "FakeStructuredClient", "StructuredLLMClient", "StructuredLLMError"]


class StructuredLLMClient(Protocol):
    name: str
    model: str

    def complete_structured(
        self, schema: dict[str, Any], messages: list[dict[str, str]]
    ) -> dict[str, Any]: ...


class FakeStructuredClient:
    """Test adapter: returns a canned dict, or raises a canned error on demand."""

    name = "fake"
    model = "fake-model"

    def __init__(
        self,
        result: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._result = result if result is not None else {}
        self._error = error
        self.calls: list[tuple[dict[str, Any], list[dict[str, str]]]] = []

    def complete_structured(
        self, schema: dict[str, Any], messages: list[dict[str, str]]
    ) -> dict[str, Any]:
        self.calls.append((schema, messages))
        if self._error is not None:
            raise self._error
        return self._result
