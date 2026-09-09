"""Tests for candidate profile Pydantic models."""

import pytest
from pydantic import ValidationError

from app.profile.models import CandidateProfile, WorkExperience


def minimal_profile_data() -> dict[str, object]:
    """Return the smallest valid candidate profile payload."""
    return {
        "full_name": "Taylor Example",
        "contact": {"email": "taylor@example.com"},
    }


def test_valid_minimal_candidate_profile() -> None:
    profile = CandidateProfile.model_validate(minimal_profile_data())

    assert profile.full_name == "Taylor Example"
    assert profile.skills == {}
    assert profile.education == []


def test_invalid_email_is_rejected() -> None:
    data = minimal_profile_data()
    data["contact"] = {"email": "not-an-email"}

    with pytest.raises(ValidationError, match="valid email address"):
        CandidateProfile.model_validate(data)


def test_required_fields_are_enforced() -> None:
    with pytest.raises(ValidationError):
        CandidateProfile.model_validate({"contact": {"email": "taylor@example.com"}})


def test_unknown_top_level_field_is_rejected() -> None:
    data = minimal_profile_data()
    data["unverified_fact"] = "Not allowed"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CandidateProfile.model_validate(data)


def test_current_work_experience_cannot_have_an_end_date() -> None:
    with pytest.raises(ValidationError, match="end_date must be None"):
        WorkExperience(
            company="Example Co.",
            role="Engineer",
            start_date="2024-01",
            end_date="2024-12",
            is_current=True,
        )


def test_collection_defaults_are_independent() -> None:
    first = CandidateProfile.model_validate(minimal_profile_data())
    second = CandidateProfile.model_validate(minimal_profile_data())

    first.skills["languages"] = ["Python"]
    first.education.append({"institution": "Example U", "degree": "BSc"})

    assert second.skills == {}
    assert second.education == []
