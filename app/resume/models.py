"""Strict, structured models for the presentation-oriented master resume."""

from __future__ import annotations

import re
from datetime import date
from typing import Self

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


class ResumeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _text(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError("must not be blank")
    return normalized


def _optional_text(value: str | None) -> str | None:
    return None if value is None else _text(value)


def _list_text(values: list[str]) -> list[str]:
    return [_text(value) for value in values]


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    normalized = _text(value)
    if not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", normalized):
        raise ValueError("must use YYYY, YYYY-MM, or YYYY-MM-DD format")
    try:
        parts = [int(part) for part in normalized.split("-")]
        return date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)
    except ValueError as error:
        raise ValueError("must be a valid calendar date") from error


def _validate_range(start: str | None, end: str | None) -> None:
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ValueError("end_date must not be earlier than start_date")


class ResumeContact(ResumeModel):
    name: str
    email: str
    phone: str | None = None
    location: str | None = None
    linkedin_url: AnyUrl | None = None
    github_url: AnyUrl | None = None
    portfolio_url: AnyUrl | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _text(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = _text(value)
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("must be a valid email address")
        return normalized

    @field_validator("phone", "location")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class ResumeExperience(ResumeModel):
    company: str
    role: str
    location: str | None = None
    start_date: str
    end_date: str | None = None
    current: bool = False
    bullets: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)

    @field_validator("company", "role", "start_date")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _text(value)

    @field_validator("location", "end_date")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("bullets", "technologies")
    @classmethod
    def normalize_lists(cls, values: list[str]) -> list[str]:
        return _list_text(values)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        _parse_date(self.start_date)
        if self.current and self.end_date is not None:
            raise ValueError("current experience cannot have an end_date")
        if not self.current and self.end_date is None:
            raise ValueError("non-current experience requires an end_date")
        _validate_range(self.start_date, self.end_date)
        return self


class ResumeEducation(ResumeModel):
    institution: str
    degree: str
    field_of_study: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    details: list[str] = Field(default_factory=list)

    @field_validator("institution", "degree")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _text(value)

    @field_validator("field_of_study", "location", "start_date", "end_date")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("details")
    @classmethod
    def normalize_details(cls, values: list[str]) -> list[str]:
        return _list_text(values)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        _validate_range(self.start_date, self.end_date)
        return self


class ResumeProject(ResumeModel):
    name: str
    description: str
    technologies: list[str] = Field(default_factory=list)
    url: AnyUrl | None = None
    bullets: list[str] = Field(default_factory=list)

    @field_validator("name", "description")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _text(value)

    @field_validator("technologies", "bullets")
    @classmethod
    def normalize_lists(cls, values: list[str]) -> list[str]:
        return _list_text(values)


class ResumeCertification(ResumeModel):
    name: str
    issuer: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    credential_id: str | None = None
    credential_url: AnyUrl | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _text(value)

    @field_validator("issuer", "issue_date", "expiry_date", "credential_id")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        _validate_range(self.issue_date, self.expiry_date)
        return self


class ResumeAchievement(ResumeModel):
    title: str
    description: str
    date: str | None = None
    issuer: str | None = None

    @field_validator("title", "description")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _text(value)

    @field_validator("date", "issuer")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        _parse_date(value)
        return value


class MasterResume(ResumeModel):
    schema_version: str = "1.0"
    candidate_name: str
    contact: ResumeContact
    headline: str | None = None
    professional_summary: str | None = None
    skills: dict[str, list[str]] = Field(default_factory=dict)
    experience: list[ResumeExperience] = Field(default_factory=list)
    education: list[ResumeEducation] = Field(default_factory=list)
    projects: list[ResumeProject] = Field(default_factory=list)
    certifications: list[ResumeCertification] = Field(default_factory=list)
    achievements: list[ResumeAchievement] = Field(default_factory=list)

    @field_validator("schema_version", "candidate_name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _text(value)

    @field_validator("headline", "professional_summary")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, values: dict[str, list[str]]) -> dict[str, list[str]]:
        return {_text(category): _list_text(items) for category, items in values.items()}
