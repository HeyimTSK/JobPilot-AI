"""Validation helpers for structured JSON returned by an AI provider."""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.exceptions import AIOutputValidationError
from app.ai.models import AIResponse


T = TypeVar("T", bound=BaseModel)


def validate_json_response(response: AIResponse, output_model: type[T]) -> T:
    """Parse response JSON and validate it into the caller's Pydantic output model."""
    try:
        payload = json.loads(response.content)
    except json.JSONDecodeError as error:
        raise AIOutputValidationError("AI response content is not valid JSON.") from error

    try:
        return output_model.model_validate(payload)
    except ValidationError as error:
        raise AIOutputValidationError(
            "AI response content does not satisfy the requested output schema."
        ) from error
