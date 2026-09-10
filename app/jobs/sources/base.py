"""Interfaces for job discovery sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.jobs.models import Job


class JobSource(ABC):
    """Contract that every permitted job discovery source must implement."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the stable identifier for this source."""
        raise NotImplementedError

    @abstractmethod
    def discover(self, payload: Any) -> list[Job]:
        """Convert source-specific input into normalized Job records."""
        raise NotImplementedError
