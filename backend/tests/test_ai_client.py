from unittest.mock import patch

import httpx
import pytest

from app.core.config import Settings
from app.services.ai_client import AIClient, AIClientError


def _settings(**over) -> Settings:
    base = {
        "ai_enabled": True,
        "ai_base_url": "https://fake.invalid/v1",
        "ai_api_key": "sk-test",
        "ai_model": "test/model",
        "ai_timeout_s": 10,
    }
    base.update(over)
    return Settings(**base)


def _fake_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        request=httpx.Request("POST", "https://fake.invalid/chat/completions"),
        json={"choices": [{"message": {"content": content}}]},
    )


def test_disabled_without_key() -> None:
    with pytest.raises(AIClientError):
        AIClient(_settings(ai_api_key="")).complete_json([{"role": "user", "content": "hi"}])


def test_complete_json_text() -> None:
    client = AIClient(_settings())
    with patch("httpx.post", return_value=_fake_response('{"a":1}')) as post:
        assert client.complete_json([{"role": "user", "content": "hi"}]) == {"a": 1}
    payload = post.call_args.kwargs["json"]
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["temperature"] == 0


def test_bad_json_raises() -> None:
    client = AIClient(_settings())
    with (
        patch("httpx.post", return_value=_fake_response("nope")),
        pytest.raises(AIClientError),
    ):
        client.complete_json([{"role": "user", "content": "hi"}])
