"""Exceptions for deterministic proposal validation and human approval."""

from app.resume.exceptions import ResumeError


class ResumeApprovalError(ResumeError):
    """Base exception for approval operations."""


class ResumeApprovalRejectedError(ResumeApprovalError):
    """Raised when a proposal cannot be approved because validation failed."""
