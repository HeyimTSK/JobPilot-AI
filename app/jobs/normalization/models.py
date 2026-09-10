"""Models for source-specific job data before normalization."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field


class RawJobData(BaseModel):
    """Validated source data that has not yet been normalized into a Job."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    url: AnyUrl

    source: str = Field(min_length=1)
    source_job_id: str | None = None

    location: str = Field(min_length=1)
    remote_status: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None

    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    salary_currency: str | None = None

    description: str = Field(min_length=1)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)

    application_url: AnyUrl | None = None
    application_deadline: date | None = None
    posted_at: date | None = None
