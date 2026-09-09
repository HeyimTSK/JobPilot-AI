"""Exceptions raised by the candidate profile domain."""


class ProfileError(Exception):
    """Base exception for candidate profile operations."""


class ProfileNotFoundError(ProfileError):
    """Raised when a requested candidate profile file does not exist."""


class ProfileValidationError(ProfileError):
    """Raised when candidate profile data is invalid or cannot be parsed."""


class ProfilePersistenceError(ProfileError):
    """Raised when a candidate profile cannot be safely saved."""
