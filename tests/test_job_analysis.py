"""Tests for AI-assisted structured job analysis."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.ai.exceptions import AIOutputValidationError, AIProviderError
from app.ai.models import AIRequest, AIResponse
from app.ai.provider import AIProvider
from app.jobs.analysis.models import JobAnalysis, JobRecommendation
from app.jobs.analysis.service import JobAnalyzer, analyze_job
from app.jobs.exceptions import JobValidationError
from app.jobs.matching.models import MatchDecision, MatchResult, MatchScoreBreakdown
from app.jobs.models import EmploymentType, ExperienceLevel, Job, RemoteStatus
from app.profile.models import CandidateProfile


class FakeProvider(AIProvider):
    def __init__(self, response: AIResponse | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.requests: list[AIRequest] = []

    def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.response


def make_profile() -> CandidateProfile:
    return CandidateProfile.model_validate({
        "full_name": "Taylor Example",
        "contact": {"email": "taylor@example.com"},
        "current_title": "Python Engineer",
        "professional_summary": "Backend engineer building services.",
        "skills": {"languages": ["Python"], "databases": ["SQL"]},
        "experience": [{
            "company": "Example Co", "role": "Engineer", "start_date": "2022-01",
            "responsibilities": ["Built APIs"], "technologies": ["Python", "SQL"],
        }],
        "projects": [{
            "name": "API Project", "description": "A verified API project.",
            "technologies": ["Python"],
        }],
    })


def make_job() -> Job:
    return Job.model_validate({
        "job_title": "Senior Python Engineer", "company_name": "Example Co",
        "job_url": "https://example.com/jobs/1", "source": "company_site",
        "location": "Remote", "remote_status": RemoteStatus.REMOTE,
        "employment_type": EmploymentType.FULL_TIME,
        "experience_level": ExperienceLevel.SENIOR,
        "description": "Build backend services.",
        "required_skills": ["Python", "SQL", "Docker"],
        "preferred_skills": ["Kubernetes"],
    })


def make_match_result() -> MatchResult:
    return MatchResult(
        score=55,
        decision=MatchDecision.POSSIBLE_MATCH,
        breakdown=MatchScoreBreakdown(
            required_skills=26.67, target_role=15, preferred_skills=0,
            experience_level=10, employment_type=0, remote_preference=0, location=3,
        ),
        matched_required_skills=["Python", "SQL"],
        missing_required_skills=["Docker"],
        reasons=["Matched 2 of 3 required skills."],
        warnings=["Docker not found in verified profile."],
    )


def make_response(content: str | None = None) -> AIResponse:
    return AIResponse(
        content=content or (
            '{"role_summary":"Senior backend role.","strengths":["Python"],'
            '"concerns":["Docker is not verified."],"skill_gaps":["Docker"],'
            '"relevant_experience":["Built APIs at Example Co."],'
            '"recommendation":"consider","confidence":0.82}'
        ),
        provider="fake", model="test-model",
    )


def test_valid_analysis_response_is_validated_and_returned():
    provider = FakeProvider(response=make_response())

    result = JobAnalyzer(provider).analyze(make_profile(), make_job(), make_match_result())

    assert isinstance(result, JobAnalysis)
    assert result.recommendation is JobRecommendation.CONSIDER
    assert result.confidence == 0.82


def test_request_contains_candidate_job_and_authoritative_match_context():
    provider = FakeProvider(response=make_response())
    profile, job, match = make_profile(), make_job(), make_match_result()

    JobAnalyzer(provider).analyze(profile, job, match)
    request = provider.requests[0]

    assert "Python Engineer" in request.prompt
    assert "Docker" in request.prompt
    assert "Example Co" in request.prompt
    assert '"score": 55.0' in request.prompt
    assert "authoritative" in request.prompt
    assert request.metadata == {"component": "job_analysis"}


def test_request_explicitly_protects_candidate_facts():
    provider = FakeProvider(response=make_response())

    JobAnalyzer(provider).analyze(make_profile(), make_job(), make_match_result())
    instructions = provider.requests[0].system_instruction
    prompt = provider.requests[0].prompt

    for phrase in [
        "Candidate facts are authoritative",
        "Do not invent candidate skills",
        "Do not infer unsupported experience as fact",
        "Skill gaps must be based on job requirements",
        "do not change or recalculate",
        "Return ONLY the requested JSON structure",
    ]:
        assert phrase.casefold() in (instructions + prompt).casefold()


def test_service_uses_provider_neutral_interface_and_convenience_function():
    provider = FakeProvider(response=make_response())

    result = analyze_job(make_profile(), make_job(), make_match_result(), provider)

    assert isinstance(provider, AIProvider)
    assert result.role_summary == "Senior backend role."


def test_malformed_json_is_rejected():
    with pytest.raises(AIOutputValidationError):
        JobAnalyzer(FakeProvider(response=make_response("not json"))).analyze(
            make_profile(), make_job(), make_match_result()
        )


def test_schema_invalid_json_is_rejected():
    content = '{"role_summary":"ok","recommendation":"unknown","confidence":2}'

    with pytest.raises(AIOutputValidationError):
        JobAnalyzer(FakeProvider(response=make_response(content))).analyze(
            make_profile(), make_job(), make_match_result()
        )


def test_provider_error_is_preserved_as_provider_error():
    failure = AIProviderError("provider unavailable")

    with pytest.raises(AIProviderError) as error:
        JobAnalyzer(FakeProvider(error=failure)).analyze(
            make_profile(), make_job(), make_match_result()
        )

    assert error.value is failure


def test_secrets_are_not_added_to_prompt_or_metadata():
    profile = make_profile()
    profile = profile.model_copy(update={"professional_summary": "safe summary"})
    provider = FakeProvider(response=make_response())

    JobAnalyzer(provider).analyze(profile, make_job(), make_match_result())
    request = provider.requests[0]

    assert "OPENAI_API_KEY" not in request.prompt
    assert "sk-" not in request.prompt
    assert "OPENAI_API_KEY" not in str(request.metadata)
    assert "sk-" not in str(request.metadata)


@pytest.mark.parametrize("bad_profile, bad_job, bad_match", [
    (object(), make_job(), make_match_result()),
    (make_profile(), object(), make_match_result()),
    (make_profile(), make_job(), object()),
])
def test_invalid_domain_inputs_are_rejected(bad_profile, bad_job, bad_match):
    with pytest.raises(JobValidationError):
        JobAnalyzer(FakeProvider(response=make_response())).analyze(
            bad_profile, bad_job, bad_match
        )


def test_invalid_provider_is_rejected():
    with pytest.raises(JobValidationError):
        JobAnalyzer(object())


def test_job_analysis_rejects_unknown_fields_and_invalid_recommendation():
    with pytest.raises(ValidationError):
        JobAnalysis(
            role_summary="summary", recommendation="consider", confidence=0.5,
            unexpected="not allowed",
        )
    with pytest.raises(ValidationError):
        JobAnalysis(role_summary="summary", recommendation="maybe", confidence=0.5)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_job_analysis_rejects_confidence_out_of_bounds(confidence):
    with pytest.raises(ValidationError):
        JobAnalysis(role_summary="summary", recommendation="consider", confidence=confidence)


def test_job_analysis_uses_safe_list_defaults_and_is_frozen():
    result = JobAnalysis(role_summary="summary", recommendation="consider", confidence=0.5)

    assert result.strengths == []
    with pytest.raises(ValidationError):
        result.role_summary = "changed"
