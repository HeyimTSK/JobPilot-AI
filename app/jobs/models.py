"""Pydantic models and deterministic identity helpers for normalized jobs."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Self

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


class RemoteStatus(str, Enum):
    """Where a job is expected to be performed."""

    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class EmploymentType(str, Enum):
    """The engagement type advertised for a job."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    APPRENTICESHIP = "apprenticeship"


class ExperienceLevel(str, Enum):
    """The seniority level advertised for a job."""

    INTERNSHIP = "internship"
    ENTRY_LEVEL = "entry_level"
    ASSOCIATE = "associate"
    MID_LEVEL = "mid_level"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"
    DIRECTOR = "director"
    EXECUTIVE = "executive"


class JobApplicationStatus(str, Enum):
    """A job's current position in the candidate's application workflow."""

    DISCOVERED = "discovered"
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class JobModel(BaseModel):
    """Base model that prevents unrecognized job data from being accepted."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def normalize_fingerprint_component(value: str) -> str:
    """Return a stable, punctuation-insensitive representation for a key field."""
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return " ".join(re.findall(r"[^\W_]+", normalized, flags=re.UNICODE))


def create_job_fingerprint(company_name: str, job_title: str, location: str) -> str:
    """Create a process-stable SHA-256 fingerprint for duplicate detection."""
    components = (
        normalize_fingerprint_component(company_name),
        normalize_fingerprint_component(job_title),
        normalize_fingerprint_component(location),
    )
    fingerprint_input = "\x1f".join(components).encode("utf-8")
    return hashlib.sha256(fingerprint_input).hexdigest()


class Job(JobModel):
    """A validated, normalized internal representation of a job opportunity."""

    id: int | None = Field(default=None, ge=1)

    job_title: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    job_url: AnyUrl
    source: str = Field(min_length=1)
    source_job_id: str | None = None

    location: str = Field(min_length=1)
    remote_status: RemoteStatus
    employment_type: EmploymentType
    experience_level: ExperienceLevel
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    salary_currency: str | None = None
    description: str = Field(min_length=1)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)

    application_url: AnyUrl | None = None
    application_deadline: date | None = None

    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    posted_at: date | None = None
    fingerprint: str = ""
    status: JobApplicationStatus = JobApplicationStatus.DISCOVERED

    @field_validator(
        "job_title", "company_name", "source", "location", "description", mode="before"
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """Trim required strings and reject values that become empty."""
        if not isinstance(value, str):
            return value
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("must not be blank")
        return normalized_value

    @field_validator("source_job_id")
    @classmethod
    def strip_optional_source_id(cls, value: str | None) -> str | None:
        """Normalize optional source job IDs without turning blanks into identities."""
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("salary_currency", mode="before")
    @classmethod
    def normalize_salary_currency(cls, value: object) -> str | None:
        """Store only uppercase, alphabetic ISO-style three-letter currency codes."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("must be a three-letter alphabetic currency code")
        normalized_value = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", normalized_value):
            raise ValueError("must be a three-letter alphabetic currency code")
        return normalized_value

    @field_validator("required_skills", "preferred_skills")
    @classmethod
    def validate_skill_lists(cls, values: list[str]) -> list[str]:
        """Ensure skills are non-empty, normalized strings."""
        normalized_values = []
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise ValueError("must contain only non-blank strings")
            normalized_values.append(value.strip())
        return normalized_values

    @model_validator(mode="after")
    def validate_salary_and_fingerprint(self) -> Self:
        """Validate related salary fields and derive the canonical fingerprint."""
        if self.salary_min is not None and self.salary_max is not None:
            if self.salary_min > self.salary_max:
                raise ValueError("salary_min must not exceed salary_max")
        if (self.salary_min is not None or self.salary_max is not None) and not self.salary_currency:
            raise ValueError("salary_currency is required when salary values are provided")

        object.__setattr__(
            self,
            "fingerprint",
            create_job_fingerprint(self.company_name, self.job_title, self.location),
        )
        return self
