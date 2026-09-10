"""Tests for strict normalized job Pydantic models."""

from datetime import timezone

import pytest
from pydantic import ValidationError

from app.jobs.models import (
    EmploymentType,
    ExperienceLevel,
    Job,
    JobApplicationStatus,
    RemoteStatus,
    create_job_fingerprint,
)


def valid_job_data() -> dict[str, object]:
    """Return the smallest complete valid job payload."""
    return {
        "job_title": "Backend Engineer",
        "company_name": "Example Systems",
        "job_url": "https://careers.example.com/jobs/backend-engineer",
        "source": "example_company_careers",
        "location": "Example City, Example State",
        "remote_status": "hybrid",
        "employment_type": "full_time",
        "experience_level": "mid_level",
        "description": "Build reliable fictional backend services.",
    }


def test_valid_job_creation_derives_fingerprint_and_defaults() -> None:
    job = Job.model_validate(valid_job_data())

    assert job.id is None
    assert job.fingerprint == create_job_fingerprint(
        "Example Systems", "Backend Engineer", "Example City, Example State"
    )
    assert job.required_skills == []
    assert job.preferred_skills == []
    assert job.status is JobApplicationStatus.DISCOVERED
    assert job.discovered_at.tzinfo is timezone.utc


def test_unknown_job_field_is_rejected() -> None:
    data = valid_job_data()
    data["untrusted_external_field"] = "not allowed"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Job.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("remote_status", "mostly_remote"),
        ("employment_type", "permanent"),
        ("experience_level", "principal"),
        ("status", "pending_review"),
    ],
)
def test_invalid_enum_values_are_rejected(field: str, value: str) -> None:
    data = valid_job_data()
    data[field] = value

    with pytest.raises(ValidationError):
        Job.model_validate(data)


def test_enum_fields_are_stored_as_expected_enum_members() -> None:
    job = Job.model_validate(valid_job_data())

    assert job.remote_status is RemoteStatus.HYBRID
    assert job.employment_type is EmploymentType.FULL_TIME
    assert job.experience_level is ExperienceLevel.MID_LEVEL


def test_fingerprint_is_consistent_across_equivalent_calls() -> None:
    first = create_job_fingerprint("Example Systems", "Backend Engineer", "Example City")
    second = create_job_fingerprint("Example Systems", "Backend Engineer", "Example City")

    assert first == second
    assert len(first) == 64


def test_fingerprint_normalizes_case_whitespace_and_punctuation() -> None:
    first = create_job_fingerprint("Example Systems, Inc.", "Backend Engineer", "New York, NY")
    second = create_job_fingerprint("  example systems inc ", "backend-engineer", "new york ny")

    assert first == second


def test_supplied_fingerprint_is_recomputed_from_identity_fields() -> None:
    data = valid_job_data()
    data["fingerprint"] = "untrusted-value"

    job = Job.model_validate(data)

    assert job.fingerprint != "untrusted-value"


@pytest.mark.parametrize("field", ["company_name", "job_title", "location"])
def test_identity_fields_are_immutable_after_fingerprint_derivation(field: str) -> None:
    job = Job.model_validate(valid_job_data())

    with pytest.raises(ValidationError, match="Instance is frozen"):
        setattr(job, field, "Changed identity value")

    assert job.fingerprint == create_job_fingerprint(
        "Example Systems", "Backend Engineer", "Example City, Example State"
    )


def test_salary_requires_currency_and_valid_range() -> None:
    missing_currency = valid_job_data()
    missing_currency["salary_min"] = "100000"
    with pytest.raises(ValidationError, match="salary_currency is required"):
        Job.model_validate(missing_currency)

    reversed_range = valid_job_data()
    reversed_range.update(
        {"salary_min": "125000", "salary_max": "100000", "salary_currency": "USD"}
    )
    with pytest.raises(ValidationError, match="salary_min must not exceed"):
        Job.model_validate(reversed_range)


def test_salary_currency_is_normalized_before_validation() -> None:
    data = valid_job_data()
    data.update({"salary_min": "100000", "salary_currency": " usd "})

    assert Job.model_validate(data).salary_currency == "USD"


@pytest.mark.parametrize("currency", ["$US", 123, "US", "USDD", "U5D"])
def test_invalid_salary_currency_is_rejected(currency: object) -> None:
    data = valid_job_data()
    data.update({"salary_min": "100000", "salary_currency": currency})

    with pytest.raises(ValidationError, match="three-letter alphabetic currency code"):
        Job.model_validate(data)
