"""Provider-neutral structured resume tailoring proposals."""

from app.resume.tailoring.models import (
    ResumeSourceReference,
    TailoringAction,
    TailoringChange,
    TailoringProposal,
)
from app.resume.tailoring.service import ResumeTailoringService, tailor_resume

__all__ = [
    "ResumeSourceReference", "ResumeTailoringService", "TailoringAction",
    "TailoringChange", "TailoringProposal", "tailor_resume",
]
