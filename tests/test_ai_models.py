"""Tests for provider-neutral AI boundary models."""

import pytest
from pydantic import ValidationError

from app.ai.models import AIRequest, AIResponse, AISettings


def test_ai_request_accepts_valid_provider_neutral_data():
    request = AIRequest(
        prompt="Summarize verified facts.",
        system_instruction="Return JSON only.",
        temperature=0.2,
        max_output_tokens=200,
        metadata={"workflow": "test"},
    )

    assert request.prompt == "Summarize verified facts."
    assert request.metadata == {"workflow": "test"}


@pytest.mark.parametrize("field, value", [("prompt", "  "), ("system_instruction", " ")])
def test_ai_request_rejects_blank_text(field, value):
    data = {"prompt": "Valid", field: value}
    with pytest.raises(ValidationError):
        AIRequest(**data)


@pytest.mark.parametrize("temperature", [-0.01, 2.01])
def test_ai_request_rejects_temperature_outside_sensible_range(temperature):
    with pytest.raises(ValidationError):
        AIRequest(prompt="Valid", temperature=temperature)


@pytest.mark.parametrize("max_output_tokens", [0, -1])
def test_ai_request_rejects_non_positive_token_limit(max_output_tokens):
    with pytest.raises(ValidationError):
        AIRequest(prompt="Valid", max_output_tokens=max_output_tokens)


def test_ai_request_rejects_unknown_fields_and_is_frozen():
    with pytest.raises(ValidationError):
        AIRequest(prompt="Valid", unexpected=True)

    request = AIRequest(prompt="Valid")
    with pytest.raises(ValidationError):
        request.prompt = "Changed"


def test_ai_response_accepts_valid_data_and_is_frozen():
    response = AIResponse(
        content='{"status": "ok"}', provider="fake", model="fake-model", request_id="req-1"
    )

    assert response.request_id == "req-1"
    with pytest.raises(ValidationError):
        response.content = "Changed"


@pytest.mark.parametrize("field", ["content", "provider", "model", "request_id"])
def test_ai_response_rejects_blank_text(field):
    data = {"content": "{}", "provider": "fake", "model": "fake-model", field: "  "}
    with pytest.raises(ValidationError):
        AIResponse(**data)


def test_ai_response_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        AIResponse(content="{}", provider="fake", model="fake-model", unknown=True)


def test_ai_settings_reads_only_shared_environment_variables():
    settings = AISettings.from_environment({"AI_PROVIDER": " local ", "AI_MODEL": " test-model "})

    assert settings.provider == "local"
    assert settings.model == "test-model"


def test_ai_settings_allows_missing_environment_variables():
    settings = AISettings.from_environment({})

    assert settings.provider is None
    assert settings.model is None


def test_ai_settings_rejects_unknown_fields_and_is_frozen():
    with pytest.raises(ValidationError):
        AISettings(provider="fake", unknown=True)

    settings = AISettings(provider="fake")
    with pytest.raises(ValidationError):
        settings.provider = "other"
