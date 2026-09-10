"""Exceptions raised by the structured master resume domain."""


class ResumeError(Exception):
    """Base exception for resume operations."""


class ResumeValidationError(ResumeError):
    """Raised when resume data fails schema or consistency validation."""


class ResumeStorageError(ResumeError):
    """Raised when resume JSON cannot be read or safely written."""


class ResumeNotFoundError(ResumeError):
    """Raised when a requested resume file does not exist."""
