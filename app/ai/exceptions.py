"""Exceptions for the provider-neutral AI boundary."""


class AIError(Exception):
    """Base exception for AI integration failures."""


class AIConfigurationError(AIError):
    """Raised when AI configuration is missing or invalid."""


class AIProviderError(AIError):
    """Raised when a provider cannot fulfill an otherwise valid request."""


class AIOutputValidationError(AIError):
    """Raised when provider response content cannot satisfy an output schema."""
