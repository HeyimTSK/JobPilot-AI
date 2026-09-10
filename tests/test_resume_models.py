"""Model tests for the structured master resume domain."""

import pytest
from pydantic import ValidationError

from app.resume.models import (
    MasterResume, ResumeAchievement, ResumeCertification, ResumeContact,
    ResumeEducation, ResumeExperience, ResumeProject,
)


def contact():
    return {"name": "Jordan Example", "email": "jordan@example.com", "linkedin_url": "https://example.com/jordan"}


def resume_data():
    return {"candidate_name": "Jordan Example", "contact": contact()}


def test_valid_master_resume_and_serialization_round_trip():
    resume = MasterResume.model_validate(resume_data())
    restored = MasterResume.model_validate_json(resume.model_dump_json())
    assert restored == resume
    assert restored.experience == []


def test_required_blank_and_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        MasterResume.model_validate({"contact": contact()})
    with pytest.raises(ValidationError):
        MasterResume.model_validate({"candidate_name": " ", "contact": contact()})
    with pytest.raises(ValidationError):
        MasterResume.model_validate({**resume_data(), "unknown": True})


def test_invalid_urls_are_rejected():
    with pytest.raises(ValidationError):
        ResumeContact(name="Jordan", email="jordan@example.com", github_url="not a url")


def test_experience_date_and_current_rules():
    base = {"company": "Example", "role": "Engineer", "start_date": "2022-01"}
    assert ResumeExperience(**base, current=True).end_date is None
    with pytest.raises(ValidationError):
        ResumeExperience(**base, current=True, end_date="2023-01")
    with pytest.raises(ValidationError):
        ResumeExperience(**base, current=False)
    with pytest.raises(ValidationError):
        ResumeExperience(**base, current=False, end_date="2021-01")
    with pytest.raises(ValidationError):
        ResumeExperience(**{**base, "start_date": "2022-13"}, current=True)


def test_education_projects_certifications_and_achievements():
    assert ResumeEducation(institution="Institute", degree="Degree", details=[" Detail "]).details == ["Detail"]
    assert ResumeProject(name="Project", description="Description", technologies=[" Python "]).technologies == ["Python"]
    assert ResumeCertification(name="Cert", issue_date="2023-01", expiry_date="2024-01")
    assert ResumeAchievement(title="Award", description="Description", date="2023-01")
    with pytest.raises(ValidationError):
        ResumeCertification(name="Cert", issue_date="2024-01", expiry_date="2023-01")


def test_lists_defaults_order_and_immutability():
    resume = MasterResume.model_validate({**resume_data(), "skills": {"first": ["One", "Two"], "second": ["Three"]}})
    assert list(resume.skills) == ["first", "second"]
    assert resume.skills["first"] == ["One", "Two"]
    with pytest.raises(ValidationError):
        resume.candidate_name = "Changed"


def test_lists_reject_blank_items():
    with pytest.raises(ValidationError):
        ResumeProject(name="Project", description="Description", bullets=[" "])
