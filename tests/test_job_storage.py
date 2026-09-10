"""Tests for SQLite job persistence."""

import sqlite3
from pathlib import Path

import pytest

from app.jobs.exceptions import (
    DuplicateJobError,
    JobNotFoundError,
    JobStorageError,
    JobValidationError,
)
from app.jobs.models import Job, JobApplicationStatus
from app.jobs.storage import JobStorage, initialize_database


def valid_job_data() -> dict[str, object]:
    """Return valid data for a persisted job record."""
    return {
        "job_title": "Backend Engineer",
        "company_name": "Example Systems",
        "job_url": "https://careers.example.com/jobs/backend-engineer",
        "source": "example_company_careers",
        "source_job_id": "EXAMPLE-123",
        "location": "Example City, Example State",
        "remote_status": "hybrid",
        "employment_type": "full_time",
        "experience_level": "mid_level",
        "salary_min": "100000",
        "salary_max": "125000",
        "salary_currency": "USD",
        "description": "Build reliable fictional backend services.",
        "required_skills": ["Python", "SQL"],
        "preferred_skills": ["FastAPI"],
        "application_url": "https://careers.example.com/jobs/backend-engineer/apply",
        "application_deadline": "2026-12-31",
        "posted_at": "2026-09-01",
    }


def make_storage(tmp_path: Path) -> JobStorage:
    """Return storage backed by an isolated test database."""
    return JobStorage(tmp_path / "nested" / "jobs.db")


def test_database_initialization_creates_schema_and_parent_directory(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "jobs.db"

    initialize_database(database_path)

    assert database_path.is_file()
    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
    assert {"id", "fingerprint", "status"}.issubset(columns)


def test_database_initialization_wraps_filesystem_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "unavailable" / "jobs.db"

    def raise_filesystem_error(*args: object, **kwargs: object) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "mkdir", raise_filesystem_error)

    with pytest.raises(JobStorageError, match="Unable to initialize job database"):
        initialize_database(database_path)


def test_job_insertion_assigns_id_and_retrieval_by_id(tmp_path: Path) -> None:
    storage = make_storage(tmp_path)

    inserted = storage.insert_job(Job.model_validate(valid_job_data()))
    retrieved = storage.get_job_by_id(inserted.id or 0)

    assert inserted.id is not None
    assert retrieved == inserted
    assert retrieved.required_skills == ["Python", "SQL"]


def test_job_retrieval_by_fingerprint_and_listing(tmp_path: Path) -> None:
    storage = make_storage(tmp_path)
    inserted = storage.insert_job(Job.model_validate(valid_job_data()))

    assert storage.get_job_by_fingerprint(inserted.fingerprint) == inserted
    assert storage.list_jobs() == [inserted]


def test_duplicate_job_fingerprint_is_rejected_atomically(tmp_path: Path) -> None:
    storage = make_storage(tmp_path)
    first = Job.model_validate(valid_job_data())
    duplicate_data = valid_job_data()
    duplicate_data["job_url"] = "https://another-source.example/jobs/999"
    duplicate_data["source"] = "another_source"

    storage.insert_job(first)
    with pytest.raises(DuplicateJobError, match="same normalized company, title, and location"):
        storage.insert_job(Job.model_validate(duplicate_data))

    assert len(storage.list_jobs()) == 1


def test_job_status_update_persists_and_returns_updated_job(tmp_path: Path) -> None:
    storage = make_storage(tmp_path)
    inserted = storage.insert_job(Job.model_validate(valid_job_data()))

    updated = storage.update_job_status(inserted.id or 0, JobApplicationStatus.APPLIED)

    assert updated.status is JobApplicationStatus.APPLIED
    assert storage.get_job_by_id(inserted.id or 0).status is JobApplicationStatus.APPLIED


def test_missing_jobs_raise_meaningful_not_found_errors(tmp_path: Path) -> None:
    storage = make_storage(tmp_path)

    with pytest.raises(JobNotFoundError, match="ID 999 was not found"):
        storage.get_job_by_id(999)
    with pytest.raises(JobNotFoundError, match="requested fingerprint was not found"):
        storage.get_job_by_fingerprint("missing")
    with pytest.raises(JobNotFoundError, match="ID 999 was not found"):
        storage.update_job_status(999, JobApplicationStatus.SAVED)


def test_invalid_status_and_unvalidated_insert_are_rejected(tmp_path: Path) -> None:
    storage = make_storage(tmp_path)

    with pytest.raises(JobValidationError, match="valid JobApplicationStatus"):
        storage.update_job_status(1, "invalid")  # type: ignore[arg-type]
    with pytest.raises(JobValidationError, match="validated Job"):
        storage.insert_job(valid_job_data())  # type: ignore[arg-type]


def test_corrupt_persisted_skills_json_raises_storage_error(tmp_path: Path) -> None:
    storage = make_storage(tmp_path)
    inserted = storage.insert_job(Job.model_validate(valid_job_data()))

    with sqlite3.connect(storage.database_path) as connection:
        connection.execute(
            "UPDATE jobs SET required_skills = ? WHERE id = ?", ("{not valid json", inserted.id)
        )

    with pytest.raises(JobStorageError, match="invalid or corrupt"):
        storage.get_job_by_id(inserted.id or 0)
