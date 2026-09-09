"""Tests for candidate profile file persistence."""

import json
from pathlib import Path

import pytest

from app.profile.exceptions import ProfileNotFoundError, ProfileValidationError
from app.profile.service import create_profile, load_profile, save_profile


def valid_profile_data() -> dict[str, object]:
    """Return valid JSON-compatible profile data for service tests."""
    return {
        "full_name": "Jordan Example",
        "contact": {"email": "jordan@example.com"},
        "skills": {"languages": ["Python"]},
    }


def test_load_valid_profile_json(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(valid_profile_data()), encoding="utf-8")

    profile = load_profile(profile_path)

    assert profile.contact.email == "jordan@example.com"


def test_missing_profile_file_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(ProfileNotFoundError, match="was not found"):
        load_profile(tmp_path / "missing.json")


def test_invalid_json_raises_validation_error(tmp_path: Path) -> None:
    profile_path = tmp_path / "invalid.json"
    profile_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ProfileValidationError, match="valid JSON"):
        load_profile(profile_path)


def test_invalid_profile_schema_raises_validation_error(tmp_path: Path) -> None:
    profile_path = tmp_path / "invalid-schema.json"
    profile_path.write_text('{"full_name": "Jordan Example"}', encoding="utf-8")

    with pytest.raises(ProfileValidationError, match="Invalid candidate profile"):
        load_profile(profile_path)


def test_save_and_reload_profile(tmp_path: Path) -> None:
    profile = create_profile(valid_profile_data())
    profile_path = tmp_path / "profile.json"

    save_profile(profile, profile_path)

    assert load_profile(profile_path) == profile


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    profile = create_profile(valid_profile_data())
    profile_path = tmp_path / "new" / "nested" / "profile.json"

    save_profile(profile, profile_path)

    assert profile_path.is_file()
