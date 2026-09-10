"""Abstract provider contract isolated from provider SDKs and transports."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.models import AIRequest, AIResponse


class AIProvider(ABC):
    """Provider-neutral synchronous AI generation interface."""

    @abstractmethod
    def generate(self, request: AIRequest) -> AIResponse:
        """Generate one provider-neutral response for a validated request."""
        raise NotImplementedError
