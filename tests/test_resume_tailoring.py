"""Tests for human-reviewed provider-neutral resume tailoring proposals."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from app.ai.exceptions import AIOutputValidationError, AIProviderError
from app.ai.models import AIRequest, AIResponse
from app.ai.provider import AIProvider
from app.jobs.analysis.models import JobAnalysis
from app.jobs.matching.service import JobMatcher
from app.jobs.models import EmploymentType, ExperienceLevel, Job, RemoteStatus
from app.profile.models import CandidateProfile
from app.resume.exceptions import ResumeValidationError
from app.resume.models import MasterResume
from app.resume.tailoring.models import (
    ResumeSourceReference, ResumeSourceType, TailoringAction, TailoringChange, TailoringProposal,
)
from app.resume.tailoring.service import ResumeTailoringService, validate_tailoring_proposal


class FakeProvider(AIProvider):
    def __init__(self, content: str | None = None, error: Exception | None = None):
        self.content = content or '{"target_job_fingerprint":"PLACEHOLDER"}'
        self.error = error
        self.requests: list[AIRequest] = []

    def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        if self.error:
            raise self.error
        return AIResponse(content=self.content, provider="fake", model="test")


def make_profile() -> CandidateProfile:
    return CandidateProfile.model_validate({
        "full_name": "Jordan Example", "contact": {"email": "jordan@example.com"},
        "current_title": "Python Engineer", "skills": {"languages": ["Python", "SQL"]},
        "experience": [{
            "company": "Example Co", "role": "Engineer", "start_date": "2022-01",
            "is_current": True, "technologies": ["Python", "SQL"],
            "responsibilities": ["Built APIs"],
        }],
    })


def make_resume() -> MasterResume:
    return MasterResume.model_validate({
        "candidate_name": "Jordan Example",
        "contact": {"name": "Jordan Example", "email": "jordan@example.com"},
        "skills": {"languages": ["Python", "SQL"]},
        "experience": [{
            "company": "Example Co", "role": "Engineer", "start_date": "2022-01",
            "current": True, "bullets": ["Built reliable APIs"], "technologies": ["Python", "SQL"],
        }],
        "projects": [{"name": "API Project", "description": "A verified API project.", "technologies": ["Python"]}],
    })


def make_job() -> Job:
    return Job.model_validate({
        "job_title": "Python Engineer", "company_name": "Example Co",
        "job_url": "https://example.com/job", "source": "example", "location": "Remote",
        "remote_status": RemoteStatus.REMOTE, "employment_type": EmploymentType.FULL_TIME,
        "experience_level": ExperienceLevel.SENIOR, "description": "Build APIs.",
        "required_skills": ["Python", "SQL"], "preferred_skills": [],
    })


def make_analysis() -> JobAnalysis:
    return JobAnalysis(role_summary="Python role", recommendation="recommended", confidence=0.8)


def make_proposal(job: Job, **overrides) -> str:
    data = {
        "schema_version": "1.0", "target_job_fingerprint": job.fingerprint,
        "professional_summary": "Python engineer focused on APIs.",
        "selected_skills": ["Python"],
        "changes": [{
            "action": "rewrite", "section": "experience",
            "source_reference": {"source_type": "resume", "source_path": "resume.experience[0].bullets[0]"},
            "original_text": "Built reliable APIs", "proposed_text": "Built reliable APIs for production services.",
            "rationale": "Aligns the existing bullet with the role.",
        }],
        "warnings": [], "requires_human_review": True,
    }
    data.update(overrides)
    import json
    return json.dumps(data)


def service_and_inputs(provider=None):
    profile, resume, job = make_profile(), make_resume(), make_job()
    match = JobMatcher().match(profile, job)
    provider = provider or FakeProvider(make_proposal(job))
    return ResumeTailoringService(provider), profile, resume, job, match, make_analysis()


def test_source_reference_validation_and_supported_types():
    assert ResumeSourceReference(source_type="profile", source_path="profile.skills[languages][0]")
    assert ResumeSourceReference(source_type="resume", source_path="resume.experience[0].bullets[0]")
    with pytest.raises(ValidationError):
        ResumeSourceReference(source_type="other", source_path="x")
    with pytest.raises(ValidationError):
        ResumeSourceReference(source_type="profile", source_path=" ")


def test_tailoring_change_rules_and_actions():
    ref = {"source_type": "resume", "source_path": "resume.experience[0].bullets[0]"}
    change = TailoringChange(action="rewrite", section="experience", source_reference=ref,
                             original_text="old", proposed_text="new", rationale="clearer")
    assert change.action is TailoringAction.REWRITE
    with pytest.raises(ValidationError):
        TailoringChange(action="unknown", section="experience", source_reference=ref, original_text="old", rationale="why")
    with pytest.raises(ValidationError):
        TailoringChange(action="rewrite", section="experience", source_reference=ref, original_text="old", rationale="why")
    assert TailoringChange(action="remove", section="experience", source_reference=ref, original_text="old", rationale="irrelevant")
    with pytest.raises(ValidationError):
        TailoringChange(action="remove", section="experience", source_reference=ref, original_text="old", proposed_text="x", rationale="bad")


def test_proposal_model_requires_review_and_rejects_unknown_or_blank_values():
    job = make_job()
    with pytest.raises(ValidationError):
        TailoringProposal(target_job_fingerprint=job.fingerprint, professional_summary="summary", requires_human_review=False)
    with pytest.raises(ValidationError):
        TailoringProposal(target_job_fingerprint=job.fingerprint, professional_summary="summary", unexpected=True)
    with pytest.raises(ValidationError):
        TailoringProposal(target_job_fingerprint=" ", professional_summary="summary")


def test_valid_tailoring_proposal_is_returned():
    service, profile, resume, job, match, analysis = service_and_inputs()
    result = service.propose(profile, resume, job, match, analysis)
    assert isinstance(result, TailoringProposal)
    assert result.requires_human_review is True


def test_request_contains_all_context_and_safety_instructions():
    service, profile, resume, job, match, analysis = service_and_inputs()
    provider = service._provider
    service.propose(profile, resume, job, match, analysis)
    request = provider.requests[0]
    for value in ["Python", "Built reliable APIs", job.fingerprint, str(match.score), "Python role"]:
        assert value in request.prompt
    for phrase in ["Candidate facts are authoritative", "Do not invent facts", "Every proposed change must reference", "authoritative", "human review", "Return only"]:
        assert phrase.casefold() in (request.prompt + request.system_instruction).casefold()
    assert request.metadata == {"component": "resume_tailoring"}
    assert "jordan@example.com" not in request.prompt
    assert "OPENAI_API_KEY" not in request.prompt
    assert "sk-" not in str(request.metadata)


def test_provider_contract_is_used_without_network():
    service, profile, resume, job, match, analysis = service_and_inputs()
    assert isinstance(service._provider, AIProvider)
    assert service.propose(profile, resume, job, match, analysis).target_job_fingerprint == job.fingerprint


def test_provider_errors_propagate_and_malformed_output_is_distinct():
    service, profile, resume, job, match, analysis = service_and_inputs(FakeProvider(error=AIProviderError("offline")))
    with pytest.raises(AIProviderError):
        service.propose(profile, resume, job, match, analysis)
    bad = FakeProvider("not json")
    service, profile, resume, job, match, analysis = service_and_inputs(bad)
    with pytest.raises(AIOutputValidationError):
        service.propose(profile, resume, job, match, analysis)


@pytest.mark.parametrize("override", [
    {"target_job_fingerprint": "wrong"},
    {"selected_skills": ["Kubernetes"]},
    {"changes": [{
        "action": "rewrite", "section": "experience",
        "source_reference": {"source_type": "resume", "source_path": "resume.experience[0].bullets[99]"},
        "original_text": "Built reliable APIs", "proposed_text": "new", "rationale": "why",
    }]},
    {"changes": [{
        "action": "rewrite", "section": "experience",
        "source_reference": {"source_type": "resume", "source_path": "resume.experience[0].bullets[0]"},
        "original_text": "wrong", "proposed_text": "new", "rationale": "why",
    }]},
])
def test_deterministic_output_validation_rejects_invalid_proposals(override):
    service, profile, resume, job, match, analysis = service_and_inputs(FakeProvider(make_proposal(job=make_job(), **override)))
    # Rebuild response for the actual job fingerprint where needed.
    provider = FakeProvider(make_proposal(job, **override))
    service = ResumeTailoringService(provider)
    with pytest.raises(ResumeValidationError):
        service.propose(profile, resume, job, match, analysis)


def test_match_result_must_correspond_to_profile_and_job():
    service, profile, resume, job, match, analysis = service_and_inputs()
    changed = match.model_copy(update={"score": 1})
    with pytest.raises(ResumeValidationError):
        service.propose(profile, resume, job, changed, analysis)


@pytest.mark.parametrize("bad", [object(), None])
def test_invalid_inputs_are_rejected(bad):
    service, profile, resume, job, match, analysis = service_and_inputs()
    with pytest.raises(ResumeValidationError):
        service.propose(bad, resume, job, match, analysis)


def test_inputs_are_not_mutated():
    service, profile, resume, job, match, analysis = service_and_inputs()
    snapshots = [copy.deepcopy(value.model_dump(mode="json")) for value in [profile, resume, job, match]]
    service.propose(profile, resume, job, match, analysis)
    assert [value.model_dump(mode="json") for value in [profile, resume, job, match]] == snapshots


def test_schema_invalid_output_is_rejected():
    service, profile, resume, job, match, analysis = service_and_inputs(FakeProvider(make_proposal(make_job(), selected_skills=["Unknown"])))
    with pytest.raises(ResumeValidationError):
        service.propose(profile, resume, job, match, analysis)
