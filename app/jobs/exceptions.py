"""Exceptions raised by the job data and storage domain."""


class JobError(Exception):
    """Base exception for job-domain operations."""


class JobValidationError(JobError):
    """Raised when supplied job data is invalid."""


class JobStorageError(JobError):
    """Raised when a job database operation cannot be completed safely."""


class JobNotFoundError(JobError):
    """Raised when a requested job record does not exist."""


class DuplicateJobError(JobError):
    """Raised when an insert would duplicate an existing job fingerprint."""
