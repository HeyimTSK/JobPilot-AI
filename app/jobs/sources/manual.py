"""Manual job discovery source."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.jobs.exceptions import JobValidationError
from app.jobs.models import Job
from app.jobs.sources.base import JobSource


class ManualJobSource(JobSource):
    """Create normalized jobs from user-provided structured job data."""

    @property
    def source_name(self) -> str:
        """Return the stable source identifier."""
        return "manual"

    def discover(self, payload: Any) -> list[Job]:
        """Validate one or more user-provided job payloads."""
        if isinstance(payload, dict):
            payloads = [payload]
        elif isinstance(payload, list):
            payloads = payload
        else:
            raise JobValidationError(
                "Manual job discovery expects a job dictionary or a list of dictionaries."
            )

        jobs: list[Job] = []

        for index, item in enumerate(payloads):
            if not isinstance(item, dict):
                raise JobValidationError(
                    f"Manual job payload at index {index} must be a dictionary."
                )

            try:
                jobs.append(Job.model_validate(item))
            except ValidationError as error:
                raise JobValidationError(
                    f"Manual job payload at index {index} is invalid."
                ) from error

        return jobs
