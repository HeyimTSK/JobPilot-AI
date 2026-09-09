"""Pydantic models for verified candidate profile data."""

from __future__ import annotations

import re
from typing import Self

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


class ProfileModel(BaseModel):
    """Base model that prevents unrecognized candidate data from being accepted."""

    model_config = ConfigDict(extra="forbid")


class ContactInformation(ProfileModel):
    """Ways to contact a candidate and optional professional links."""

    email: str
    phone: str | None = None
    location: str | None = None
    linkedin_url: AnyUrl | None = None
    github_url: AnyUrl | None = None
    portfolio_url: AnyUrl | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Validate a practical email-address format without optional dependencies."""
        normalized_value = value.strip()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized_value):
            raise ValueError("must be a valid email address")
        return normalized_value


class Education(ProfileModel):
    """A single education record."""

    institution: str = Field(min_length=1)
    degree: str = Field(min_length=1)
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    cgpa: str | None = None
    description: str | None = None


class WorkExperience(ProfileModel):
    """A single work-experience record."""

    company: str = Field(min_length=1)
    role: str = Field(min_length=1)
    employment_type: str | None = None
    location: str | None = None
    start_date: str = Field(min_length=1)
    end_date: str | None = None
    is_current: bool = False
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def current_role_has_no_end_date(self) -> Self:
        """Ensure current roles do not also declare an end date."""
        if self.is_current and self.end_date is not None:
            raise ValueError("end_date must be None when is_current is true")
        return self


class Project(ProfileModel):
    """A candidate project with its verified details."""

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    technologies: list[str] = Field(default_factory=list)
    repository_url: AnyUrl | None = None
    live_url: AnyUrl | None = None
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)


class Certification(ProfileModel):
    """A certification held by the candidate."""

    name: str = Field(min_length=1)
    issuer: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    credential_id: str | None = None
    credential_url: AnyUrl | None = None


class JobPreferences(ProfileModel):
    """A candidate's stated job-search preferences."""

    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    remote_preference: str | None = None
    employment_types: list[str] = Field(default_factory=list)
    minimum_salary: str | None = None
    experience_level: str | None = None


class CandidateProfile(ProfileModel):
    """The validated source of truth for verified candidate information."""

    full_name: str = Field(min_length=1)
    preferred_name: str | None = None
    contact: ContactInformation
    current_title: str | None = None
    professional_summary: str | None = None
    years_of_experience: float | None = None
    skills: dict[str, list[str]] = Field(default_factory=dict)
    education: list[Education] = Field(default_factory=list)
    experience: list[WorkExperience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    job_preferences: JobPreferences | None = None
