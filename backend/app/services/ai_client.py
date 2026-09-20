"""OpenAI-compatible text + structured clients for import structure recognition.

- ``AIClient.complete_json`` is the *legacy* free-text ``json_object`` path, kept
  for backward compatibility with ``question_ingest.py`` until production ingest
  switches to the Exam pipeline. It raises ``AIClientError``.
- ``AIClient.complete_structured`` is the schema-constrained path (OpenAI
  ``response_format=json_schema``) used by the LLM semantic extractor (ticket 04).
  It raises ``StructuredLLMError``.
"""

from __future__ import annotations

import json
from typing import Any, cast

import httpx

from app.core.config import Settings


class AIClientError(Exception):
    """Any legacy free-text AI failure; callers must fall back to rule-based parsing."""


class StructuredLLMError(Exception):
    """A schema-constrained structured call failed (provider / schema / decode)."""


class AIClient:
    name = "openai-compatible"

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.ai_base_url.rstrip("/")
        self.api_key = settings.ai_api_key
        self.model = settings.ai_model
        self.timeout = settings.ai_timeout_s
        self.enabled = settings.ai_enabled and bool(self.api_key)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return cast(dict[str, Any], resp.json())
        except httpx.HTTPError as exc:
            raise StructuredLLMError(str(exc)) from exc

    @staticmethod
    def _content(body: dict[str, Any]) -> str:
        return cast(str, body["choices"][0]["message"]["content"])

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        if not self.enabled:
            raise AIClientError("AI not enabled or no API key")
        try:
            body = self._post(
                {
                    "model": self.model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                }
            )
            return cast(dict[str, Any], json.loads(self._content(body)))
        except StructuredLLMError as exc:
            raise AIClientError(str(exc)) from exc
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise AIClientError(str(exc)) from exc

    def complete_structured(
        self, schema: dict[str, Any], messages: list[dict[str, str]]
    ) -> dict[str, Any]:
        """Schema-constrained completion returning the decoded JSON object."""
        if not self.enabled:
            raise StructuredLLMError("AI not enabled or no API key")
        try:
            body = self._post(
                {
                    "model": self.model,
                    "messages": messages,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "semantic_extraction",
                            "schema": schema,
                            "strict": True,
                        },
                    },
                    "temperature": 0,
                }
            )
            return cast(dict[str, Any], json.loads(self._content(body)))
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise StructuredLLMError(str(exc)) from exc
