"""Tests for job discovery source adapters."""

import pytest

from app.jobs.exceptions import DuplicateJobError, JobValidationError
from app.jobs.models import Job
from app.jobs.sources import JobSource, ManualJobSource
from app.jobs.storage import JobStorage


def valid_job_payload() -> dict:
    """Return a minimal valid manual job payload."""
    return {
        "job_title": "Python Developer",
        "company_name": "Example Technologies",
        "job_url": "https://example.com/jobs/python-developer",
        "source": "manual",
        "location": "Pune, India",
        "remote_status": "hybrid",
        "employment_type": "full_time",
        "experience_level": "entry_level",
        "description": "Build and maintain Python applications.",
    }


def test_manual_source_has_stable_name() -> None:
    source = ManualJobSource()

    assert source.source_name == "manual"


def test_manual_source_implements_job_source_contract() -> None:
    source = ManualJobSource()

    assert isinstance(source, JobSource)


def test_manual_source_discovers_single_job() -> None:
    source = ManualJobSource()

    jobs = source.discover(valid_job_payload())

    assert len(jobs) == 1
    assert isinstance(jobs[0], Job)
    assert jobs[0].job_title == "Python Developer"
    assert jobs[0].company_name == "Example Technologies"
    assert jobs[0].source == "manual"
    assert jobs[0].fingerprint


def test_manual_source_discovers_multiple_jobs() -> None:
    source = ManualJobSource()

    first = valid_job_payload()
    second = valid_job_payload()
    second["job_title"] = "Backend Developer"

    jobs = source.discover([first, second])

    assert len(jobs) == 2
    assert jobs[0].job_title == "Python Developer"
    assert jobs[1].job_title == "Backend Developer"


def test_manual_source_rejects_non_mapping_payload() -> None:
    source = ManualJobSource()

    with pytest.raises(JobValidationError):
        source.discover("not a job")


def test_manual_source_rejects_invalid_job_payload() -> None:
    source = ManualJobSource()

    payload = valid_job_payload()
    del payload["company_name"]

    with pytest.raises(JobValidationError):
        source.discover(payload)


def test_manual_source_rejects_invalid_item_in_list() -> None:
    source = ManualJobSource()

    payload = valid_job_payload()

    with pytest.raises(JobValidationError):
        source.discover([payload, "not a job"])


def test_discovered_job_can_be_stored_and_retrieved(tmp_path) -> None:
    source = ManualJobSource()
    storage = JobStorage(tmp_path / "jobs.db")

    discovered_job = source.discover(valid_job_payload())[0]
    stored_job = storage.insert_job(discovered_job)
    retrieved_job = storage.get_job_by_id(stored_job.id)

    assert stored_job.id is not None
    assert retrieved_job == stored_job
    assert retrieved_job.source == "manual"
    assert retrieved_job.fingerprint == discovered_job.fingerprint


def test_discovered_duplicate_is_rejected_by_storage(tmp_path) -> None:
    source = ManualJobSource()
    storage = JobStorage(tmp_path / "jobs.db")

    first_job = source.discover(valid_job_payload())[0]
    second_job = source.discover(valid_job_payload())[0]

    storage.insert_job(first_job)

    with pytest.raises(DuplicateJobError):
        storage.insert_job(second_job)
