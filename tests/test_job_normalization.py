"""Tests for deterministic job normalization."""

from datetime import date
from decimal import Decimal

import pytest

from app.jobs.exceptions import JobValidationError
from app.jobs.models import EmploymentType, ExperienceLevel, RemoteStatus
from app.jobs.normalization.models import RawJobData
from app.jobs.normalization.service import JobNormalizer


def valid_raw_job() -> dict:
    """Return representative raw job data."""
    return {
        "title": "  Junior Python Developer  ",
        "company": "  Example Technologies  ",
        "url": "https://example.com/jobs/python-developer",
        "source": "greenhouse",
        "source_job_id": "  job-123  ",
        "location": "  Pune, Maharashtra  ",
        "remote_status": "Fully Remote",
        "employment_type": "Full-Time",
        "experience_level": "Junior",
        "salary_min": "500000",
        "salary_max": "800000",
        "salary_currency": " usd ",
        "description": "  Build Python applications.  ",
        "required_skills": [" Python ", "SQL"],
        "preferred_skills": ["  Docker   Compose "],
        "application_url": "https://example.com/apply/python",
        "application_deadline": date(2026, 10, 1),
        "posted_at": date(2026, 9, 1),
    }


def test_raw_job_data_validates_source_payload() -> None:
    raw = RawJobData.model_validate(valid_raw_job())

    assert raw.title == "  Junior Python Developer  "
    assert raw.company == "  Example Technologies  "
    assert raw.source_job_id == "  job-123  "


def test_normalizer_maps_fields_and_enum_values() -> None:
    normalizer = JobNormalizer()

    job = normalizer.normalize(valid_raw_job())

    assert job.job_title == "Junior Python Developer"
    assert job.company_name == "Example Technologies"
    assert job.location == "Pune, Maharashtra"
    assert job.remote_status == RemoteStatus.REMOTE
    assert job.employment_type == EmploymentType.FULL_TIME
    assert job.experience_level == ExperienceLevel.ENTRY_LEVEL


def test_normalizer_normalizes_salary_and_currency() -> None:
    job = JobNormalizer().normalize(valid_raw_job())

    assert job.salary_min == Decimal("500000")
    assert job.salary_max == Decimal("800000")
    assert job.salary_currency == "USD"


def test_normalizer_cleans_skills_without_changing_content() -> None:
    job = JobNormalizer().normalize(valid_raw_job())

    assert job.required_skills == ["Python", "SQL"]
    assert job.preferred_skills == ["Docker Compose"]


def test_normalizer_preserves_source_provenance() -> None:
    job = JobNormalizer().normalize(valid_raw_job())

    assert job.source == "greenhouse"
    assert job.source_job_id == "job-123"
    assert str(job.job_url) == "https://example.com/jobs/python-developer"
    assert str(job.application_url) == "https://example.com/apply/python"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("remote", RemoteStatus.REMOTE),
        ("WORK FROM HOME", RemoteStatus.REMOTE),
        ("wfh", RemoteStatus.REMOTE),
        ("Hybrid Work", RemoteStatus.HYBRID),
        ("on-site", RemoteStatus.ONSITE),
        ("On Site", RemoteStatus.ONSITE),
    ],
)
def test_normalizer_supports_remote_variants(
    value: str, expected: RemoteStatus
) -> None:
    payload = valid_raw_job()
    payload["remote_status"] = value

    job = JobNormalizer().normalize(payload)

    assert job.remote_status == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("full time", EmploymentType.FULL_TIME),
        ("FULL-TIME", EmploymentType.FULL_TIME),
        ("contractor", EmploymentType.CONTRACT),
        ("temp", EmploymentType.TEMPORARY),
        ("intern", EmploymentType.INTERNSHIP),
        ("apprentice", EmploymentType.APPRENTICESHIP),
    ],
)
def test_normalizer_supports_employment_variants(
    value: str, expected: EmploymentType
) -> None:
    payload = valid_raw_job()
    payload["employment_type"] = value

    job = JobNormalizer().normalize(payload)

    assert job.employment_type == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("intern", ExperienceLevel.INTERNSHIP),
        ("entry-level", ExperienceLevel.ENTRY_LEVEL),
        ("junior", ExperienceLevel.ENTRY_LEVEL),
        ("associate", ExperienceLevel.ASSOCIATE),
        ("mid-level", ExperienceLevel.MID_LEVEL),
        ("sr", ExperienceLevel.SENIOR),
        ("lead", ExperienceLevel.LEAD),
        ("manager", ExperienceLevel.MANAGER),
    ],
)
def test_normalizer_supports_experience_variants(
    value: str, expected: ExperienceLevel
) -> None:
    payload = valid_raw_job()
    payload["experience_level"] = value

    job = JobNormalizer().normalize(payload)

    assert job.experience_level == expected


def test_normalizer_rejects_unknown_remote_status() -> None:
    payload = valid_raw_job()
    payload["remote_status"] = "mostly remote"

    with pytest.raises(JobValidationError):
        JobNormalizer().normalize(payload)


def test_normalizer_rejects_unknown_employment_type() -> None:
    payload = valid_raw_job()
    payload["employment_type"] = "freelance-ish"

    with pytest.raises(JobValidationError):
        JobNormalizer().normalize(payload)


def test_normalizer_rejects_unknown_experience_level() -> None:
    payload = valid_raw_job()
    payload["experience_level"] = "principal"

    with pytest.raises(JobValidationError):
        JobNormalizer().normalize(payload)


def test_normalizer_requires_normalizable_classification_fields() -> None:
    payload = valid_raw_job()

    payload["remote_status"] = None

    with pytest.raises(JobValidationError):
        JobNormalizer().normalize(payload)


def test_normalizer_rejects_invalid_raw_data() -> None:
    payload = valid_raw_job()
    del payload["title"]

    with pytest.raises(JobValidationError):
        JobNormalizer().normalize(payload)


def test_normalizer_rejects_blank_skill() -> None:
    payload = valid_raw_job()
    payload["required_skills"] = ["Python", "   "]

    with pytest.raises(JobValidationError):
        JobNormalizer().normalize(payload)


def test_normalizer_generates_deterministic_fingerprint() -> None:
    first = JobNormalizer().normalize(valid_raw_job())
    second = JobNormalizer().normalize(valid_raw_job())

    assert first.fingerprint == second.fingerprint


def test_normalizer_accepts_raw_job_model() -> None:
    raw = RawJobData.model_validate(valid_raw_job())

    job = JobNormalizer().normalize(raw)

    assert job.job_title == "Junior Python Developer"
    assert job.source == "greenhouse"
