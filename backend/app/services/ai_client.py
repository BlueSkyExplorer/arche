"""Minimal OpenAI-compatible text client, used ONLY for import structure recognition.

Callers treat any AIClientError as "no AI answer" and fall back to rules.
"""
from __future__ import annotations

import json
from typing import Any, cast

import httpx

from app.core.config import Settings


class AIClientError(Exception):
    """Any AI failure; callers must fall back to rule-based parsing."""


class AIClient:
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.ai_base_url.rstrip("/")
        self.api_key = settings.ai_api_key
        self.model = settings.ai_model
        self.timeout = settings.ai_timeout_s
        self.enabled = settings.ai_enabled and bool(self.api_key)

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        if not self.enabled:
            raise AIClientError("AI not enabled or no API key")
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return cast(dict[str, Any], json.loads(content))
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise AIClientError(str(exc)) from exc
