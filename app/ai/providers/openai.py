"""OpenAI Responses API adapter for JobPilot's provider-neutral AI boundary."""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI, OpenAIError

from app.ai.exceptions import AIConfigurationError, AIProviderError
from app.ai.models import AIRequest, AIResponse, AISettings
from app.ai.provider import AIProvider


DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


class OpenAIProvider(AIProvider):
    """Synchronous OpenAI adapter using the Responses API without tools or streaming."""

    def __init__(self, settings: AISettings | None = None, client: OpenAI | None = None) -> None:
        """Configure the adapter from injected settings and OPENAI_API_KEY when needed."""
        self._settings = settings or AISettings.from_environment()
        self._model = self._settings.model or DEFAULT_OPENAI_MODEL

        if client is not None:
            self._client = client
            return

        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise AIConfigurationError("OpenAI provider requires OPENAI_API_KEY configuration.")
        self._client = OpenAI(api_key=api_key, max_retries=0)

    def generate(self, request: AIRequest) -> AIResponse:
        """Generate one response through OpenAI's synchronous Responses API."""
        request_options: dict[str, Any] = {"model": self._model, "input": request.prompt}
        if request.system_instruction is not None:
            request_options["instructions"] = request.system_instruction
        if request.temperature is not None:
            request_options["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            request_options["max_output_tokens"] = request.max_output_tokens

        try:
            response = self._client.responses.create(**request_options)
        except OpenAIError as error:
            raise AIProviderError("OpenAI provider failed to generate a response.") from error

        content = getattr(response, "output_text", None)
        if not isinstance(content, str) or not content.strip():
            raise AIProviderError("OpenAI provider returned no text content.")

        response_model = getattr(response, "model", None)
        if not isinstance(response_model, str) or not response_model.strip():
            raise AIProviderError("OpenAI provider returned no model identifier.")

        request_id = getattr(response, "id", None)
        if request_id is not None and (not isinstance(request_id, str) or not request_id.strip()):
            raise AIProviderError("OpenAI provider returned an invalid response identifier.")

        metadata: dict[str, str] = {}
        status = getattr(response, "status", None)
        if isinstance(status, str) and status.strip():
            metadata["status"] = status

        return AIResponse(
            content=content,
            provider="openai",
            model=response_model,
            request_id=request_id,
            metadata=metadata or None,
        )
