"""Pydantic models for deterministic job matching results."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MatchModel(BaseModel):
    """Base model that rejects unexpected matching data."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class MatchDecision(str, Enum):
    """Overall compatibility classification."""

    STRONG_MATCH = "strong_match"
    POSSIBLE_MATCH = "possible_match"
    WEAK_MATCH = "weak_match"


class MatchScoreBreakdown(MatchModel):
    """Individual components contributing to the overall match score."""

    required_skills: float = Field(ge=0, le=40)
    target_role: float = Field(ge=0, le=15)
    preferred_skills: float = Field(ge=0, le=10)
    experience_level: float = Field(ge=0, le=10)
    employment_type: float = Field(ge=0, le=10)
    remote_preference: float = Field(ge=0, le=10)
    location: float = Field(ge=0, le=5)

    @property
    def total(self) -> float:
        """Return the total deterministic match score."""
        return round(
            self.required_skills
            + self.target_role
            + self.preferred_skills
            + self.experience_level
            + self.employment_type
            + self.remote_preference
            + self.location,
            2,
        )


class MatchResult(MatchModel):
    """Explainable deterministic compatibility result."""

    score: float = Field(ge=0, le=100)
    decision: MatchDecision
    breakdown: MatchScoreBreakdown

    matched_required_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    matched_preferred_skills: list[str] = Field(default_factory=list)

    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)