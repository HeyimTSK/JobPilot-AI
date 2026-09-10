"""JSON persistence and basic identity validation for master resumes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from pydantic import ValidationError

from app.profile.models import CandidateProfile
from app.resume.exceptions import ResumeNotFoundError, ResumeStorageError, ResumeValidationError
from app.resume.models import MasterResume


def _format_validation_error(error: ValidationError) -> str:
    details = []
    for detail in error.errors():
        location = ".".join(str(part) for part in detail["loc"])
        details.append(f"{location}: {detail['msg']}")
    return "; ".join(details)


def create_resume(data: dict[str, Any]) -> MasterResume:
    """Validate mapping data and return a master resume."""
    try:
        return MasterResume.model_validate(data)
    except ValidationError as error:
        raise ResumeValidationError(
            f"Invalid master resume: {_format_validation_error(error)}"
        ) from None


def load_resume(path: Path | str) -> MasterResume:
    """Load, parse, and validate one master resume JSON file."""
    resume_path = Path(path)
    if not resume_path.is_file():
        raise ResumeNotFoundError(f"Master resume file was not found: {resume_path}")
    try:
        with resume_path.open("r", encoding="utf-8") as resume_file:
            data = json.load(resume_file)
    except json.JSONDecodeError as error:
        raise ResumeStorageError(f"Master resume JSON is malformed: '{resume_path}'.") from None
    except (OSError, UnicodeDecodeError) as error:
        raise ResumeStorageError(f"Unable to read master resume '{resume_path}'.") from None
    if not isinstance(data, dict):
        raise ResumeValidationError("Master resume JSON must contain an object at its root.")
    return create_resume(data)


def save_resume(resume: MasterResume, path: Path | str) -> None:
    """Atomically save a validated master resume as UTF-8 JSON."""
    if not isinstance(resume, MasterResume):
        raise ResumeValidationError("Only a validated MasterResume can be saved.")

    resume_path = Path(path)
    temporary_path: Path | None = None
    try:
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=resume_path.parent,
            prefix=f".{resume_path.name}.", suffix=".tmp", delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(resume.model_dump(mode="json"), temporary_file, indent=2, ensure_ascii=False)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, resume_path)
    except (OSError, TypeError, ValueError) as error:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise ResumeStorageError(f"Unable to save master resume to '{resume_path}'.") from None


def get_default_resume_path() -> Path:
    """Return the default user-managed master resume location."""
    return Path(__file__).resolve().parents[2] / "data" / "master_resume.json"


def validate_resume_identity(resume: MasterResume, profile: CandidateProfile) -> None:
    """Ensure basic presentation identity agrees with the verified profile."""
    if not isinstance(resume, MasterResume):
        raise ResumeValidationError("Only a validated MasterResume can be checked.")
    if not isinstance(profile, CandidateProfile):
        raise ResumeValidationError("Only a validated CandidateProfile can be checked.")
    if resume.candidate_name.casefold() != profile.full_name.casefold():
        raise ResumeValidationError("Master resume candidate name does not match the profile.")
    if resume.contact.email.casefold() != profile.contact.email.casefold():
        raise ResumeValidationError("Master resume contact email does not match the profile.")
