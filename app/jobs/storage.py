"""SQLite persistence for validated job records."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import ValidationError

from app.jobs.exceptions import (
    DuplicateJobError,
    JobNotFoundError,
    JobStorageError,
    JobValidationError,
)
from app.jobs.models import Job, JobApplicationStatus


def get_default_database_path() -> Path:
    """Return the default local SQLite database path for job records."""
    return Path(__file__).resolve().parents[2] / "data" / "jobs.db"


class JobStorage:
    """A small transaction-safe repository backed by a SQLite database."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = Path(database_path) if database_path is not None else get_default_database_path()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize_database(self) -> None:
        """Create the jobs database and schema if they do not already exist."""
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_title TEXT NOT NULL,
                        company_name TEXT NOT NULL,
                        job_url TEXT NOT NULL,
                        source TEXT NOT NULL,
                        source_job_id TEXT,
                        location TEXT NOT NULL,
                        remote_status TEXT NOT NULL,
                        employment_type TEXT NOT NULL,
                        experience_level TEXT NOT NULL,
                        salary_min TEXT,
                        salary_max TEXT,
                        salary_currency TEXT,
                        description TEXT NOT NULL,
                        required_skills TEXT NOT NULL,
                        preferred_skills TEXT NOT NULL,
                        application_url TEXT,
                        application_deadline TEXT,
                        discovered_at TEXT NOT NULL,
                        posted_at TEXT,
                        fingerprint TEXT NOT NULL UNIQUE,
                        status TEXT NOT NULL
                    )
                    """
                )
        except (OSError, sqlite3.Error) as error:
            raise JobStorageError(
                f"Unable to initialize job database at '{self.database_path}'."
            ) from error

    def insert_job(self, job: Job) -> Job:
        """Atomically insert a validated job and return it with its database ID."""
        if not isinstance(job, Job):
            raise JobValidationError("Only a validated Job can be inserted.")

        self.initialize_database()
        payload = job.model_dump(mode="json")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    INSERT INTO jobs (
                        job_title, company_name, job_url, source, source_job_id,
                        location, remote_status, employment_type, experience_level,
                        salary_min, salary_max, salary_currency, description,
                        required_skills, preferred_skills, application_url,
                        application_deadline, discovered_at, posted_at, fingerprint, status
                    ) VALUES (
                        :job_title, :company_name, :job_url, :source, :source_job_id,
                        :location, :remote_status, :employment_type, :experience_level,
                        :salary_min, :salary_max, :salary_currency, :description,
                        :required_skills, :preferred_skills, :application_url,
                        :application_deadline, :discovered_at, :posted_at, :fingerprint, :status
                    )
                    """,
                    {
                        **payload,
                        "required_skills": json.dumps(payload["required_skills"]),
                        "preferred_skills": json.dumps(payload["preferred_skills"]),
                    },
                )
        except sqlite3.IntegrityError as error:
            if "fingerprint" in str(error).lower():
                raise DuplicateJobError(
                    "A job with the same normalized company, title, and location already exists."
                ) from None
            raise JobStorageError("Unable to insert job because database constraints were violated.") from error
        except sqlite3.Error as error:
            raise JobStorageError(f"Unable to insert job into '{self.database_path}'.") from error

        return job.model_copy(update={"id": cursor.lastrowid})

    def get_job_by_id(self, job_id: int) -> Job:
        """Return a job by its database ID."""
        return self._get_one("id = ?", (job_id,), f"Job with ID {job_id} was not found.")

    def get_job_by_fingerprint(self, fingerprint: str) -> Job:
        """Return a job by its deterministic duplicate-detection fingerprint."""
        return self._get_one(
            "fingerprint = ?", (fingerprint,), "Job with the requested fingerprint was not found."
        )

    def _get_one(self, condition: str, parameters: tuple[object, ...], message: str) -> Job:
        self.initialize_database()
        try:
            with self._connect() as connection:
                row = connection.execute(
                    f"SELECT * FROM jobs WHERE {condition}", parameters
                ).fetchone()
        except sqlite3.Error as error:
            raise JobStorageError(f"Unable to retrieve a job from '{self.database_path}'.") from error
        if row is None:
            raise JobNotFoundError(message)
        return self._job_from_row(row)

    def list_jobs(self) -> list[Job]:
        """Return all jobs, newest discoveries first, with a stable ID tiebreaker."""
        self.initialize_database()
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM jobs ORDER BY discovered_at DESC, id DESC"
                ).fetchall()
        except sqlite3.Error as error:
            raise JobStorageError(f"Unable to list jobs from '{self.database_path}'.") from error
        return [self._job_from_row(row) for row in rows]

    def update_job_status(self, job_id: int, status: JobApplicationStatus) -> Job:
        """Atomically update a job's application status and return the updated job."""
        if not isinstance(status, JobApplicationStatus):
            try:
                status = JobApplicationStatus(status)
            except (TypeError, ValueError):
                raise JobValidationError("Job status must be a valid JobApplicationStatus value.") from None

        self.initialize_database()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    "UPDATE jobs SET status = ? WHERE id = ?", (status.value, job_id)
                )
                if cursor.rowcount == 0:
                    raise JobNotFoundError(f"Job with ID {job_id} was not found.")
        except JobNotFoundError:
            raise
        except sqlite3.Error as error:
            raise JobStorageError(f"Unable to update job status in '{self.database_path}'.") from error
        return self.get_job_by_id(job_id)

    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> Job:
        """Rehydrate and validate a database row as a Job model."""
        payload = dict(row)
        try:
            payload["required_skills"] = json.loads(payload["required_skills"])
            payload["preferred_skills"] = json.loads(payload["preferred_skills"])
            return Job.model_validate(payload)
        except (TypeError, json.JSONDecodeError, ValidationError) as error:
            raise JobStorageError("A stored job record is invalid or corrupt.") from error


def initialize_database(database_path: Path | str | None = None) -> None:
    """Initialize a jobs database at the requested or default path."""
    JobStorage(database_path).initialize_database()


def insert_job(job: Job, database_path: Path | str | None = None) -> Job:
    """Insert a validated job into the requested or default database."""
    return JobStorage(database_path).insert_job(job)


def get_job_by_id(job_id: int, database_path: Path | str | None = None) -> Job:
    """Retrieve a job by ID from the requested or default database."""
    return JobStorage(database_path).get_job_by_id(job_id)


def get_job_by_fingerprint(fingerprint: str, database_path: Path | str | None = None) -> Job:
    """Retrieve a job by fingerprint from the requested or default database."""
    return JobStorage(database_path).get_job_by_fingerprint(fingerprint)


def list_jobs(database_path: Path | str | None = None) -> list[Job]:
    """List jobs from the requested or default database."""
    return JobStorage(database_path).list_jobs()


def update_job_status(
    job_id: int, status: JobApplicationStatus, database_path: Path | str | None = None
) -> Job:
    """Update a job status in the requested or default database."""
    return JobStorage(database_path).update_job_status(job_id, status)
