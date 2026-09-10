"""Job discovery source adapters."""

from app.jobs.sources.base import JobSource
from app.jobs.sources.manual import ManualJobSource

__all__ = ["JobSource", "ManualJobSource"]
