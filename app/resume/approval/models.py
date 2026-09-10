"""Immutable models representing validation results and explicit approval."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.resume.tailoring.models import ResumeSourceReference, TailoringProposal


class ApprovalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _text(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError("must not be blank")
    return normalized


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ValidationIssue(ApprovalModel):
    code: str
    message: str
    source_reference: ResumeSourceReference | None = None

    @field_validator("code", "message")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _text(value)


class ValidationResult(ApprovalModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class ApprovalDecision(ApprovalModel):
    status: ApprovalStatus
    reviewed_at: datetime
    reviewer: str
    note: str | None = None

    @field_validator("reviewed_at")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("reviewer")
    @classmethod
    def validate_reviewer(cls, value: str) -> str:
        return _text(value)

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str | None) -> str | None:
        return None if value is None else _text(value)

    @field_validator("status")
    @classmethod
    def validate_final_status(cls, value: ApprovalStatus) -> ApprovalStatus:
        if value == ApprovalStatus.PENDING:
            raise ValueError("approval decisions must be approved or rejected")
        return value


class ApprovedTailoringProposal(ApprovalModel):
    proposal: TailoringProposal
    target_job_fingerprint: str
    approved_at: datetime
    reviewer: str
    approval_note: str | None = None

    @field_validator("target_job_fingerprint", "reviewer")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _text(value)

    @field_validator("approved_at")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("approval_note")
    @classmethod
    def validate_note(cls, value: str | None) -> str | None:
        return None if value is None else _text(value)
