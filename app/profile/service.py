"""File-based persistence for validated candidate profiles."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from pydantic import ValidationError

from app.profile.exceptions import (
    ProfileNotFoundError,
    ProfilePersistenceError,
    ProfileValidationError,
)
from app.profile.models import CandidateProfile


def _format_validation_error(error: ValidationError) -> str:
    """Return useful validation details without including submitted values."""
    details = []
    for detail in error.errors():
        location = ".".join(str(part) for part in detail["loc"])
        details.append(f"{location}: {detail['msg']}")
    return "; ".join(details)


def create_profile(data: dict[str, Any]) -> CandidateProfile:
    """Validate mapping data and return a candidate profile."""
    try:
        return CandidateProfile.model_validate(data)
    except ValidationError as error:
        raise ProfileValidationError(
            f"Invalid candidate profile: {_format_validation_error(error)}"
        ) from None


def load_profile(path: Path | str) -> CandidateProfile:
    """Load, parse, and validate a candidate profile JSON file."""
    profile_path = Path(path)
    if not profile_path.is_file():
        raise ProfileNotFoundError(f"Candidate profile file was not found: {profile_path}")

    try:
        with profile_path.open("r", encoding="utf-8") as profile_file:
            data = json.load(profile_file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProfileValidationError(
            f"Unable to read valid JSON from candidate profile '{profile_path}'."
        ) from None

    if not isinstance(data, dict):
        raise ProfileValidationError("Candidate profile JSON must contain an object at its root.")
    return create_profile(data)


def save_profile(profile: CandidateProfile, path: Path | str) -> None:
    """Atomically save a validated candidate profile as UTF-8 JSON."""
    if not isinstance(profile, CandidateProfile):
        raise ProfilePersistenceError("Only a validated CandidateProfile can be saved.")

    profile_path = Path(path)
    temporary_path: Path | None = None
    try:
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=profile_path.parent,
            prefix=f".{profile_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(profile.model_dump(mode="json"), temporary_file, indent=2, ensure_ascii=False)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, profile_path)
    except (OSError, TypeError, ValueError) as error:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise ProfilePersistenceError(
            f"Unable to save candidate profile to '{profile_path}'."
        ) from None


def get_default_profile_path() -> Path:
    """Return the default, user-managed candidate profile location."""
    return Path(__file__).resolve().parents[2] / "data" / "candidate_profile.json"
