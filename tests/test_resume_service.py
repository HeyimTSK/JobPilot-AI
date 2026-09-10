"""Storage and identity tests for the structured master resume."""

import json
from pathlib import Path

import pytest

from app.profile.models import CandidateProfile
from app.resume.exceptions import ResumeNotFoundError, ResumeStorageError, ResumeValidationError
from app.resume.models import MasterResume
from app.resume.service import create_resume, get_default_resume_path, load_resume, save_resume, validate_resume_identity


def make_resume() -> MasterResume:
    return create_resume({
        "schema_version": "1.0", "candidate_name": "Jordan Example",
        "contact": {"name": "Jordan Example", "email": "jordan@example.com"},
        "skills": {"languages": ["Python", "SQL"]},
    })


def make_profile() -> CandidateProfile:
    return CandidateProfile.model_validate({"full_name": "Jordan Example", "contact": {"email": "jordan@example.com"}})


def test_save_load_round_trip_does_not_mutate_model(tmp_path):
    resume = make_resume()
    before = resume.model_dump(mode="json")
    path = tmp_path / "nested" / "master_resume.json"
    save_resume(resume, path)
    assert load_resume(path) == resume
    assert resume.model_dump(mode="json") == before


def test_missing_file_and_malformed_json_are_controlled(tmp_path):
    with pytest.raises(ResumeNotFoundError):
        load_resume(tmp_path / "missing.json")
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(ResumeStorageError):
        load_resume(malformed)


def test_schema_invalid_json_is_validation_error(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"candidate_name": "Only name"}), encoding="utf-8")
    with pytest.raises(ResumeValidationError):
        load_resume(path)


def test_atomic_save_leaves_no_temporary_files(tmp_path):
    path = tmp_path / "master_resume.json"
    save_resume(make_resume(), path)
    assert path.is_file()
    assert list(tmp_path.glob(".*.tmp")) == []


def test_filesystem_failure_is_controlled_and_content_is_not_exposed(monkeypatch, tmp_path):
    secret = "private-resume-detail"
    resume = make_resume().model_copy(update={"professional_summary": secret})
    monkeypatch.setattr("app.resume.service.os.replace", lambda source, target: (_ for _ in ()).throw(OSError("failed")))
    with pytest.raises(ResumeStorageError) as error:
        save_resume(resume, tmp_path / "resume.json")
    assert secret not in str(error.value)


def test_default_path_and_example_resume_are_available():
    assert get_default_resume_path().name == "master_resume.json"
    example_path = Path(__file__).resolve().parents[1] / "data" / "master_resume.example.json"
    assert load_resume(example_path).candidate_name == "Jordan Example"


def test_invalid_object_cannot_be_saved():
    with pytest.raises(ResumeValidationError):
        save_resume(object(), "resume.json")


def test_identity_validation_is_simple_and_deterministic():
    validate_resume_identity(make_resume(), make_profile())
    mismatch = make_resume().model_copy(update={"candidate_name": "Other Person"})
    with pytest.raises(ResumeValidationError):
        validate_resume_identity(mismatch, make_profile())
