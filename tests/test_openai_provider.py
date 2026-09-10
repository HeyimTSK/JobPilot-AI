"""Unit tests for the synchronous OpenAI Responses API adapter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from openai import OpenAIError

from app.ai.exceptions import AIConfigurationError, AIProviderError
from app.ai.models import AIRequest, AISettings
from app.ai.providers.openai import DEFAULT_OPENAI_MODEL, OpenAIProvider


class FakeResponses:
    """Capture Responses API arguments without making network calls."""

    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def make_client(response=None, error: Exception | None = None):
    responses = FakeResponses(response=response, error=error)
    return SimpleNamespace(responses=responses), responses


def make_sdk_response(**overrides):
    data = {
        "output_text": "Validated provider output.",
        "model": "gpt-test",
        "id": "resp_123",
        "status": "completed",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_openai_provider_generates_and_translates_a_response():
    client, responses = make_client(make_sdk_response())
    provider = OpenAIProvider(settings=AISettings(model="configured-model"), client=client)

    result = provider.generate(AIRequest(prompt="Return JSON."))

    assert responses.calls == [{"model": "configured-model", "input": "Return JSON."}]
    assert result.content == "Validated provider output."
    assert result.provider == "openai"
    assert result.model == "gpt-test"
    assert result.request_id == "resp_123"
    assert result.metadata == {"status": "completed"}


def test_openai_provider_translates_all_supported_request_options():
    client, responses = make_client(make_sdk_response())
    provider = OpenAIProvider(settings=AISettings(model="configured-model"), client=client)
    request = AIRequest(
        prompt="Return JSON.",
        system_instruction="Use verified facts only.",
        temperature=0.3,
        max_output_tokens=200,
    )

    provider.generate(request)

    assert responses.calls == [{
        "model": "configured-model",
        "input": "Return JSON.",
        "instructions": "Use verified facts only.",
        "temperature": 0.3,
        "max_output_tokens": 200,
    }]


def test_openai_provider_uses_documented_adapter_local_default_model():
    client, responses = make_client(make_sdk_response())
    provider = OpenAIProvider(settings=AISettings(), client=client)

    provider.generate(AIRequest(prompt="Return JSON."))

    assert responses.calls[0]["model"] == DEFAULT_OPENAI_MODEL


def test_openai_provider_requires_an_api_key_when_no_client_is_injected(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(AIConfigurationError) as error:
        OpenAIProvider()

    assert "OPENAI_API_KEY" in str(error.value)


def test_openai_provider_disables_sdk_retries_when_constructing_client(monkeypatch):
    created_with = {}

    def fake_openai(**kwargs):
        created_with.update(kwargs)
        return make_client(make_sdk_response())[0]

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setattr("app.ai.providers.openai.OpenAI", fake_openai)

    OpenAIProvider()

    assert created_with == {"api_key": "sk-test-key", "max_retries": 0}


def test_openai_provider_wraps_sdk_failures_without_exposing_credentials():
    secret = "sk-not-a-real-secret"
    client, _ = make_client(error=OpenAIError(f"provider failure: {secret}"))
    provider = OpenAIProvider(client=client)

    with pytest.raises(AIProviderError) as error:
        provider.generate(AIRequest(prompt="Return JSON."))

    assert error.value.__cause__ is not None
    assert secret not in str(error.value)


@pytest.mark.parametrize(
    "response",
    [make_sdk_response(output_text=""), make_sdk_response(output_text=None)],
)
def test_openai_provider_rejects_empty_or_missing_response_text(response):
    client, _ = make_client(response)

    with pytest.raises(AIProviderError, match="no text content"):
        OpenAIProvider(client=client).generate(AIRequest(prompt="Return JSON."))


def test_openai_provider_rejects_malformed_response_identifiers():
    client, _ = make_client(make_sdk_response(id=" "))

    with pytest.raises(AIProviderError, match="invalid response identifier"):
        OpenAIProvider(client=client).generate(AIRequest(prompt="Return JSON."))


def test_openai_provider_does_not_send_credentials_or_unsupported_features():
    client, responses = make_client(make_sdk_response())
    provider = OpenAIProvider(settings=AISettings(model="configured-model"), client=client)

    provider.generate(AIRequest(prompt="Return JSON.", metadata={"trace_id": "abc"}))

    assert "api_key" not in responses.calls[0]
    assert "tools" not in responses.calls[0]
    assert "stream" not in responses.calls[0]
    assert "metadata" not in responses.calls[0]
