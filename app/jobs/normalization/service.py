"""Deterministic normalization of raw job data."""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from app.jobs.exceptions import JobValidationError
from app.jobs.models import EmploymentType, ExperienceLevel, Job, RemoteStatus
from app.jobs.normalization.models import RawJobData


def _normalize_text(value: str) -> str:
    """Normalize whitespace and casing for comparison."""
    return " ".join(value.strip().casefold().split())


def _normalize_remote_status(value: str | None) -> RemoteStatus:
    """Convert recognized remote-work descriptions into the internal enum."""
    if value is None:
        raise JobValidationError("remote_status is required for normalization.")

    normalized = _normalize_text(value)

    mapping = {
        "remote": RemoteStatus.REMOTE,
        "fully remote": RemoteStatus.REMOTE,
        "work from home": RemoteStatus.REMOTE,
        "wfh": RemoteStatus.REMOTE,
        "hybrid": RemoteStatus.HYBRID,
        "hybrid work": RemoteStatus.HYBRID,
        "onsite": RemoteStatus.ONSITE,
        "on-site": RemoteStatus.ONSITE,
        "on site": RemoteStatus.ONSITE,
        "office": RemoteStatus.ONSITE,
    }

    try:
        return mapping[normalized]
    except KeyError:
        raise JobValidationError(
            f"Unsupported remote_status value: '{value}'."
        ) from None


def _normalize_employment_type(value: str | None) -> EmploymentType:
    """Convert recognized employment descriptions into the internal enum."""
    if value is None:
        raise JobValidationError("employment_type is required for normalization.")

    normalized = _normalize_text(value)

    mapping = {
        "full time": EmploymentType.FULL_TIME,
        "full-time": EmploymentType.FULL_TIME,
        "full_time": EmploymentType.FULL_TIME,
        "part time": EmploymentType.PART_TIME,
        "part-time": EmploymentType.PART_TIME,
        "part_time": EmploymentType.PART_TIME,
        "contract": EmploymentType.CONTRACT,
        "contractor": EmploymentType.CONTRACT,
        "temporary": EmploymentType.TEMPORARY,
        "temp": EmploymentType.TEMPORARY,
        "internship": EmploymentType.INTERNSHIP,
        "intern": EmploymentType.INTERNSHIP,
        "apprenticeship": EmploymentType.APPRENTICESHIP,
        "apprentice": EmploymentType.APPRENTICESHIP,
    }

    try:
        return mapping[normalized]
    except KeyError:
        raise JobValidationError(
            f"Unsupported employment_type value: '{value}'."
        ) from None


def _normalize_experience_level(value: str | None) -> ExperienceLevel:
    """Convert recognized seniority descriptions into the internal enum."""
    if value is None:
        raise JobValidationError("experience_level is required for normalization.")

    normalized = _normalize_text(value)

    mapping = {
        "internship": ExperienceLevel.INTERNSHIP,
        "intern": ExperienceLevel.INTERNSHIP,
        "entry level": ExperienceLevel.ENTRY_LEVEL,
        "entry-level": ExperienceLevel.ENTRY_LEVEL,
        "entry_level": ExperienceLevel.ENTRY_LEVEL,
        "junior": ExperienceLevel.ENTRY_LEVEL,
        "jr": ExperienceLevel.ENTRY_LEVEL,
        "associate": ExperienceLevel.ASSOCIATE,
        "mid level": ExperienceLevel.MID_LEVEL,
        "mid-level": ExperienceLevel.MID_LEVEL,
        "mid_level": ExperienceLevel.MID_LEVEL,
        "mid": ExperienceLevel.MID_LEVEL,
        "senior": ExperienceLevel.SENIOR,
        "sr": ExperienceLevel.SENIOR,
        "lead": ExperienceLevel.LEAD,
        "manager": ExperienceLevel.MANAGER,
        "director": ExperienceLevel.DIRECTOR,
        "executive": ExperienceLevel.EXECUTIVE,
    }

    try:
        return mapping[normalized]
    except KeyError:
        raise JobValidationError(
            f"Unsupported experience_level value: '{value}'."
        ) from None


def _normalize_skills(values: list[str]) -> list[str]:
    """Normalize skill whitespace while preserving source-provided wording."""
    normalized_values = []

    for value in values:
        cleaned = re.sub(r"\s+", " ", value.strip())
        if not cleaned:
            raise JobValidationError("Skills must not contain blank values.")
        normalized_values.append(cleaned)

    return normalized_values


class JobNormalizer:
    """Convert validated RawJobData into canonical Job models."""

    def normalize(self, raw_job: RawJobData | dict[str, Any]) -> Job:
        """Normalize one raw job into the canonical Job model."""
        try:
            raw = (
                raw_job
                if isinstance(raw_job, RawJobData)
                else RawJobData.model_validate(raw_job)
            )
        except ValidationError as error:
            raise JobValidationError("Raw job data is invalid.") from error

        payload = {
            "job_title": raw.title.strip(),
            "company_name": raw.company.strip(),
            "job_url": raw.url,
            "source": raw.source.strip(),
            "source_job_id": raw.source_job_id,
            "location": raw.location.strip(),
            "remote_status": _normalize_remote_status(raw.remote_status),
            "employment_type": _normalize_employment_type(raw.employment_type),
            "experience_level": _normalize_experience_level(raw.experience_level),
            "salary_min": raw.salary_min,
            "salary_max": raw.salary_max,
            "salary_currency": raw.salary_currency,
            "description": raw.description.strip(),
            "required_skills": _normalize_skills(raw.required_skills),
            "preferred_skills": _normalize_skills(raw.preferred_skills),
            "application_url": raw.application_url,
            "application_deadline": raw.application_deadline,
            "posted_at": raw.posted_at,
        }

        try:
            return Job.model_validate(payload)
        except ValidationError as error:
            raise JobValidationError("Normalized job data is invalid.") from error
