"""Tests for provider selection without network calls or provider SDK coupling."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.exceptions import AIConfigurationError
from app.ai.factory import create_ai_provider
from app.ai.models import AIRequest, AIResponse, AISettings
from app.ai.provider import AIProvider


class FakeOpenAIProvider(AIProvider):
    """In-memory stand-in used to test factory selection and settings propagation."""

    def __init__(self, settings: AISettings):
        self.settings = settings

    def generate(self, request: AIRequest) -> AIResponse:
        return AIResponse(content="{}", provider="openai", model=self.settings.model or "test")


def test_factory_selects_openai_without_constructing_a_network_client(monkeypatch):
    created: dict[str, AISettings] = {}

    def fake_provider(*, settings: AISettings):
        created["settings"] = settings
        return FakeOpenAIProvider(settings)

    monkeypatch.setattr("app.ai.factory.OpenAIProvider", fake_provider)

    provider = create_ai_provider(AISettings(provider="openai", model="configured-model"))

    assert isinstance(provider, FakeOpenAIProvider)
    assert created["settings"] == AISettings(provider="openai", model="configured-model")


def test_factory_accepts_case_insensitive_openai_provider(monkeypatch):
    monkeypatch.setattr(
        "app.ai.factory.OpenAIProvider",
        lambda *, settings: FakeOpenAIProvider(settings),
    )

    provider = create_ai_provider(AISettings(provider=" OpenAI ", model="model-a"))

    assert isinstance(provider, FakeOpenAIProvider)
    assert provider.settings.model == "model-a"


def test_factory_loads_provider_and_model_from_environment(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "environment-model")
    monkeypatch.setattr(
        "app.ai.factory.OpenAIProvider",
        lambda *, settings: FakeOpenAIProvider(settings),
    )

    provider = create_ai_provider()

    assert isinstance(provider, FakeOpenAIProvider)
    assert provider.settings.provider == "openai"
    assert provider.settings.model == "environment-model"


def test_factory_rejects_missing_provider(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)

    with pytest.raises(AIConfigurationError, match="AI_PROVIDER"):
        create_ai_provider()


@pytest.mark.parametrize("provider_name", ["", "   "])
def test_factory_rejects_blank_provider_configuration(provider_name):
    if provider_name:
        # AISettings itself rejects a supplied blank provider before the factory is called.
        with pytest.raises(ValueError):
            AISettings(provider=provider_name)
    else:
        with pytest.raises(ValueError):
            AISettings(provider=provider_name)


def test_factory_rejects_unsupported_provider_without_exposing_secrets():
    fake_secret = "sk-factory-test-secret"

    with pytest.raises(AIConfigurationError) as error:
        create_ai_provider(AISettings(provider="gemini", model=fake_secret))

    assert "Unsupported AI provider" in str(error.value)
    assert fake_secret not in str(error.value)


def test_factory_rejects_invalid_settings_argument():
    with pytest.raises(AIConfigurationError, match="validated AISettings"):
        create_ai_provider(SimpleNamespace(provider="openai"))


def test_factory_result_implements_ai_provider_contract(monkeypatch):
    monkeypatch.setattr(
        "app.ai.factory.OpenAIProvider",
        lambda *, settings: FakeOpenAIProvider(settings),
    )

    provider = create_ai_provider(AISettings(provider="openai", model="contract-model"))
    response = provider.generate(AIRequest(prompt="test"))

    assert isinstance(provider, AIProvider)
    assert response.provider == "openai"
    assert response.model == "contract-model"
