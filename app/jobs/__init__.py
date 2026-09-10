"""Normalized job data and local storage domain."""

from app.jobs.exceptions import (
    DuplicateJobError,
    JobError,
    JobNotFoundError,
    JobStorageError,
    JobValidationError,
)
from app.jobs.models import (
    EmploymentType,
    ExperienceLevel,
    Job,
    JobApplicationStatus,
    RemoteStatus,
    create_job_fingerprint,
    normalize_fingerprint_component,
)
from app.jobs.storage import (
    JobStorage,
    get_default_database_path,
    get_job_by_fingerprint,
    get_job_by_id,
    initialize_database,
    insert_job,
    list_jobs,
    update_job_status,
)

__all__ = [
    "DuplicateJobError",
    "EmploymentType",
    "ExperienceLevel",
    "Job",
    "JobApplicationStatus",
    "JobError",
    "JobNotFoundError",
    "JobStorage",
    "JobStorageError",
    "JobValidationError",
    "RemoteStatus",
    "create_job_fingerprint",
    "get_default_database_path",
    "get_job_by_fingerprint",
    "get_job_by_id",
    "initialize_database",
    "insert_job",
    "list_jobs",
    "normalize_fingerprint_component",
    "update_job_status",
]
