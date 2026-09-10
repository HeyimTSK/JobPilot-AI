"""Strict models for human-reviewed resume tailoring proposals."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TailoringModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _text(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError("must not be blank")
    return normalized


class ResumeSourceType(str, Enum):
    PROFILE = "profile"
    RESUME = "resume"


class ResumeSourceReference(TailoringModel):
    source_type: ResumeSourceType
    source_path: str

    @field_validator("source_path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        path = value.strip()
        if not path or " " in path:
            raise ValueError("source_path must be a non-empty reference path")
        return path


class TailoringAction(str, Enum):
    KEEP = "keep"
    REORDER = "reorder"
    REWRITE = "rewrite"
    REMOVE = "remove"
    EMPHASIZE = "emphasize"


class TailoringChange(TailoringModel):
    action: TailoringAction
    section: str
    source_reference: ResumeSourceReference
    original_text: str | None = None
    proposed_text: str | None = None
    rationale: str

    @field_validator("section", "rationale")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _text(value)

    @field_validator("original_text", "proposed_text")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else _text(value)

    @model_validator(mode="after")
    def validate_action_content(self) -> TailoringChange:
        if self.original_text is None:
            raise ValueError("content-derived tailoring changes require original_text")
        if self.action in {
            TailoringAction.KEEP,
            TailoringAction.REWRITE,
            TailoringAction.EMPHASIZE,
        } and self.proposed_text is None:
            raise ValueError(f"{self.action.value} changes require proposed_text")
        if self.action == TailoringAction.REWRITE and self.proposed_text is None:
            raise ValueError("rewrite changes require proposed_text")
        if self.action == TailoringAction.REMOVE and self.proposed_text is not None:
            raise ValueError("remove changes cannot contain proposed_text")
        return self


class TailoringProposal(TailoringModel):
    schema_version: str = "1.0"
    target_job_fingerprint: str
    professional_summary: str
    selected_skills: list[str] = Field(default_factory=list)
    changes: list[TailoringChange] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_human_review: bool = True

    @field_validator("schema_version", "target_job_fingerprint", "professional_summary")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _text(value)

    @field_validator("selected_skills", "warnings")
    @classmethod
    def validate_lists(cls, values: list[str]) -> list[str]:
        return [_text(value) for value in values]

    @field_validator("requires_human_review")
    @classmethod
    def require_review(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("tailoring proposals always require human review")
        return value
