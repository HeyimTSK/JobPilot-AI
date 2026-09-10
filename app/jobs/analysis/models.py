"""Validated structured output for AI-assisted job analysis."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnalysisModel(BaseModel):
    """Base model that rejects unknown fields and prevents mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _normalize_nonblank(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("must not be blank")
    return normalized


class JobRecommendation(str, Enum):
    """Allowed recommendation values for an analyzed job."""

    STRONGLY_RECOMMENDED = "strongly_recommended"
    RECOMMENDED = "recommended"
    CONSIDER = "consider"
    NOT_RECOMMENDED = "not_recommended"


class JobAnalysis(AnalysisModel):
    """Validated, non-authoritative explanation of a deterministic match."""

    role_summary: str = Field(min_length=1)
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    skill_gaps: list[str] = Field(default_factory=list)
    relevant_experience: list[str] = Field(default_factory=list)
    recommendation: JobRecommendation
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("role_summary")
    @classmethod
    def validate_role_summary(cls, value: str) -> str:
        return _normalize_nonblank(value)

    @field_validator(
        "strengths", "concerns", "skill_gaps", "relevant_experience", mode="after"
    )
    @classmethod
    def validate_list_items(cls, values: list[str]) -> list[str]:
        return [_normalize_nonblank(value) for value in values]
