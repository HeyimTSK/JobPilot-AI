"""Provider-neutral Pydantic models for AI requests, responses, and settings."""

from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIModel(BaseModel):
    """Base AI boundary model with strict, immutable input handling."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _normalize_optional_text(value: str | None) -> str | None:
    """Strip optional text while rejecting supplied blank values."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError("must not be blank when provided")
    return normalized


class AIRequest(AIModel):
    """A provider-neutral request containing no provider credentials."""

    prompt: str = Field(min_length=1)
    system_instruction: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    metadata: Mapping[str, str] | None = None

    @field_validator("prompt", "system_instruction")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)


class AIResponse(AIModel):
    """A normalized provider response awaiting optional structured validation."""

    content: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    request_id: str | None = None
    metadata: Mapping[str, str] | None = None

    @field_validator("content", "provider", "model", "request_id")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)


class AISettings(AIModel):
    """Shared provider-neutral configuration, sourced without loading secrets."""

    provider: str | None = None
    model: str | None = None

    @field_validator("provider", "model")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> AISettings:
        """Create settings from AI_PROVIDER and AI_MODEL without loading dotenv files."""
        source = os.environ if environ is None else environ
        return cls(provider=source.get("AI_PROVIDER"), model=source.get("AI_MODEL"))
