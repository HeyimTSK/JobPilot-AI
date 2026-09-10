"""Tests for the abstract AI provider and structured output validation."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai.exceptions import (
    AIConfigurationError,
    AIError,
    AIOutputValidationError,
    AIProviderError,
)
from app.ai.models import AIRequest, AIResponse
from app.ai.provider import AIProvider
from app.ai.validation import validate_json_response


class Summary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)


class FakeProvider(AIProvider):
    """In-memory test provider with no SDK, credentials, or network access."""

    def generate(self, request: AIRequest) -> AIResponse:
        return AIResponse(
            content='{"summary": "Verified profile summary."}',
            provider="fake",
            model="in-memory",
            request_id="test-request",
        )


def test_ai_provider_is_abstract():
    with pytest.raises(TypeError):
        AIProvider()


def test_fake_provider_implements_the_provider_contract():
    response = FakeProvider().generate(AIRequest(prompt="Create a summary."))

    assert response.provider == "fake"
    assert response.content == '{"summary": "Verified profile summary."}'


def test_validate_json_response_returns_validated_pydantic_model():
    result = validate_json_response(FakeProvider().generate(AIRequest(prompt="Summarize.")), Summary)

    assert isinstance(result, Summary)
    assert result.summary == "Verified profile summary."


def test_validate_json_response_wraps_invalid_json_with_chaining():
    response = AIResponse(content="not json", provider="fake", model="in-memory")

    with pytest.raises(AIOutputValidationError) as error:
        validate_json_response(response, Summary)

    assert isinstance(error.value, AIError)
    assert error.value.__cause__ is not None


def test_validate_json_response_wraps_pydantic_validation_errors_with_chaining():
    response = AIResponse(content='{"summary": ""}', provider="fake", model="in-memory")

    with pytest.raises(AIOutputValidationError) as error:
        validate_json_response(response, Summary)

    assert isinstance(error.value.__cause__, ValidationError)


def test_provider_errors_remain_distinct_from_output_validation_errors():
    assert AIProviderError is not AIOutputValidationError
    assert AIConfigurationError is not AIProviderError
    assert issubclass(AIConfigurationError, AIError)
    assert issubclass(AIProviderError, AIError)
    assert issubclass(AIOutputValidationError, AIError)
