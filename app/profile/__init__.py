"""Verified candidate profile domain."""

from app.profile.exceptions import (
    ProfileError,
    ProfileNotFoundError,
    ProfilePersistenceError,
    ProfileValidationError,
)
from app.profile.models import (
    CandidateProfile,
    Certification,
    ContactInformation,
    Education,
    JobPreferences,
    Project,
    WorkExperience,
)
from app.profile.service import (
    create_profile,
    get_default_profile_path,
    load_profile,
    save_profile,
)

__all__ = [
    "CandidateProfile",
    "Certification",
    "ContactInformation",
    "Education",
    "JobPreferences",
    "ProfileError",
    "ProfileNotFoundError",
    "ProfilePersistenceError",
    "ProfileValidationError",
    "Project",
    "WorkExperience",
    "create_profile",
    "get_default_profile_path",
    "load_profile",
    "save_profile",
]
