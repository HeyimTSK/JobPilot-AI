"""Selection of configured provider implementations."""

from __future__ import annotations

from app.ai.exceptions import AIConfigurationError
from app.ai.models import AISettings
from app.ai.provider import AIProvider
from app.ai.providers.openai import OpenAIProvider


def create_ai_provider(settings: AISettings | None = None) -> AIProvider:
    """Create the configured provider without exposing provider-specific details."""
    if settings is None:
        settings = AISettings.from_environment()
    if not isinstance(settings, AISettings):
        raise AIConfigurationError("AI provider settings must be a validated AISettings instance.")

    if settings.provider is None:
        raise AIConfigurationError("AI_PROVIDER must be configured to select an AI provider.")

    provider_name = settings.provider.casefold()
    if provider_name == "openai":
        return OpenAIProvider(settings=settings)

    raise AIConfigurationError(f"Unsupported AI provider: {settings.provider}.")
