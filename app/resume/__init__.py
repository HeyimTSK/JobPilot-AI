"""Structured master resume domain and JSON persistence."""

from app.resume.exceptions import (
    ResumeError,
    ResumeNotFoundError,
    ResumeStorageError,
    ResumeValidationError,
)
from app.resume.models import (
    MasterResume,
    ResumeAchievement,
    ResumeCertification,
    ResumeContact,
    ResumeEducation,
    ResumeExperience,
    ResumeProject,
)
from app.resume.service import (
    create_resume,
    get_default_resume_path,
    load_resume,
    save_resume,
    validate_resume_identity,
)

__all__ = [
    "MasterResume", "ResumeAchievement", "ResumeCertification", "ResumeContact",
    "ResumeEducation", "ResumeError", "ResumeExperience", "ResumeNotFoundError",
    "ResumeProject", "ResumeStorageError", "ResumeValidationError", "create_resume",
    "get_default_resume_path", "load_resume", "save_resume", "validate_resume_identity",
]
