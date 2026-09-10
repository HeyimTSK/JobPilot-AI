"""Tests for deterministic job matching models."""

import pytest
from pydantic import ValidationError

from app.jobs.matching.models import (
    MatchDecision,
    MatchResult,
    MatchScoreBreakdown,
)
from app.jobs.matching.service import JobMatcher, match_job
from app.jobs.exceptions import JobValidationError
from app.jobs.models import EmploymentType, ExperienceLevel, Job, RemoteStatus
from app.profile.models import CandidateProfile


def make_breakdown() -> MatchScoreBreakdown:
    return MatchScoreBreakdown(
        required_skills=40,
        target_role=15,
        preferred_skills=10,
        experience_level=10,
        employment_type=10,
        remote_preference=10,
        location=5,
    )


def test_breakdown_total_is_100():
    breakdown = make_breakdown()

    assert breakdown.total == 100


def test_breakdown_total_handles_partial_scores():
    breakdown = MatchScoreBreakdown(
        required_skills=20,
        target_role=10,
        preferred_skills=5,
        experience_level=7,
        employment_type=10,
        remote_preference=5,
        location=3,
    )

    assert breakdown.total == 60


def test_match_result_accepts_valid_result():
    result = MatchResult(
        score=82,
        decision=MatchDecision.STRONG_MATCH,
        breakdown=make_breakdown(),
        matched_required_skills=["Python", "SQL"],
        missing_required_skills=["Docker"],
        matched_preferred_skills=["React"],
        reasons=["Strong required-skill alignment."],
        warnings=["Docker was not found in the verified profile."],
    )

    assert result.score == 82
    assert result.decision == MatchDecision.STRONG_MATCH
    assert result.matched_required_skills == ["Python", "SQL"]


def test_breakdown_rejects_score_above_component_limit():
    with pytest.raises(ValidationError):
        MatchScoreBreakdown(
            required_skills=41,
            target_role=15,
            preferred_skills=10,
            experience_level=10,
            employment_type=10,
            remote_preference=10,
            location=5,
        )


def test_match_result_rejects_score_above_100():
    with pytest.raises(ValidationError):
        MatchResult(
            score=101,
            decision=MatchDecision.STRONG_MATCH,
            breakdown=make_breakdown(),
        )


def test_match_result_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        MatchResult(
            score=80,
            decision=MatchDecision.STRONG_MATCH,
            breakdown=make_breakdown(),
            unexpected_field="not allowed",
        )


def test_match_result_is_frozen():
    result = MatchResult(
        score=80,
        decision=MatchDecision.STRONG_MATCH,
        breakdown=make_breakdown(),
    )

    with pytest.raises(ValidationError):
        result.score = 90


def make_profile(
    *,
    skills: dict[str, list[str]] | None = None,
    experience_technologies: list[str] | None = None,
    project_technologies: list[str] | None = None,
    target_roles: list[str] | None = None,
    preferred_locations: list[str] | None = None,
    remote_preference: str | None = "Remote or hybrid",
    employment_types: list[str] | None = None,
    experience_level: str | None = "Senior",
) -> CandidateProfile:
    data = {
        "full_name": "Taylor Example",
        "contact": {"email": "taylor@example.com"},
        "skills": skills or {},
        "job_preferences": {
            "target_roles": target_roles or [],
            "preferred_locations": preferred_locations or [],
            "remote_preference": remote_preference,
            "employment_types": employment_types or [],
            "experience_level": experience_level,
        },
    }
    if experience_technologies is not None:
        data["experience"] = [{
            "company": "Example Co", "role": "Developer", "start_date": "2022-01",
            "technologies": experience_technologies,
        }]
    if project_technologies is not None:
        data["projects"] = [{
            "name": "Example Project", "description": "A verified project.",
            "technologies": project_technologies,
        }]
    return CandidateProfile.model_validate(data)


def make_job(**overrides: object) -> Job:
    data = {
        "job_title": "Senior Python Engineer",
        "company_name": "Example Co",
        "job_url": "https://example.com/jobs/1",
        "source": "company_site",
        "location": "Bengaluru, India",
        "remote_status": RemoteStatus.REMOTE,
        "employment_type": EmploymentType.FULL_TIME,
        "experience_level": ExperienceLevel.SENIOR,
        "description": "Build reliable services.",
        "required_skills": ["Python", "SQL"],
        "preferred_skills": ["Docker"],
    }
    data.update(overrides)
    return Job.model_validate(data)


def test_service_perfect_match_flattens_all_verified_skill_sources():
    profile = make_profile(
        skills={"languages": ["Python"]},
        experience_technologies=["SQL"],
        project_technologies=["Docker"],
        target_roles=["Python Engineer"],
        preferred_locations=["Bengaluru"],
        employment_types=["full-time"],
    )

    result = match_job(profile, make_job())

    assert result.score == 100
    assert result.decision is MatchDecision.STRONG_MATCH
    assert result.matched_required_skills == ["Python", "SQL"]
    assert result.matched_preferred_skills == ["Docker"]
    assert result.missing_required_skills == []


def test_service_scores_partial_and_missing_required_skills_without_claiming_absence():
    profile = make_profile(skills={"languages": ["Python"]})
    job = make_job(required_skills=["Python", "SQL", "Docker"], preferred_skills=[])

    result = match_job(profile, job)

    assert result.breakdown.required_skills == pytest.approx(13.33)
    assert result.matched_required_skills == ["Python"]
    assert result.missing_required_skills == ["SQL", "Docker"]
    assert "not found in the verified profile" in result.warnings[0]


def test_service_matches_preferred_skills_separately():
    profile = make_profile(skills={"tools": ["Docker"]})

    result = match_job(profile, make_job(required_skills=[], preferred_skills=["Docker", "Kubernetes"]))

    assert result.breakdown.required_skills == 0
    assert result.breakdown.preferred_skills == 5
    assert result.matched_preferred_skills == ["Docker"]


def test_service_matches_normalized_skills_case_and_whitespace_exactly():
    profile = make_profile(skills={"languages": ["  PYTHON   "]})

    result = match_job(profile, make_job(required_skills=["python"], preferred_skills=[]))

    assert result.breakdown.required_skills == 40
    assert result.matched_required_skills == ["python"]


def test_service_matches_target_role_conservatively_by_normalized_phrase():
    profile = make_profile(target_roles=["  Python   Engineer "])

    result = match_job(profile, make_job(required_skills=[], preferred_skills=[]))

    assert result.breakdown.target_role == 15


def test_service_matches_experience_and_employment_preferences_to_enums():
    profile = make_profile(experience_level="sr", employment_types=["full time"])

    result = match_job(profile, make_job(required_skills=[], preferred_skills=[]))

    assert result.breakdown.experience_level == 10
    assert result.breakdown.employment_type == 10


def test_service_matches_remote_or_hybrid_preference_but_not_onsite():
    profile = make_profile(remote_preference="Remote or hybrid")

    remote_result = match_job(profile, make_job(required_skills=[], preferred_skills=[]))
    onsite_result = match_job(profile, make_job(
        required_skills=[], preferred_skills=[], remote_status=RemoteStatus.ONSITE
    ))

    assert remote_result.breakdown.remote_preference == 10
    assert onsite_result.breakdown.remote_preference == 0


def test_service_matches_locations_by_normalized_text_containment():
    profile = make_profile(preferred_locations=["  bengaluru "])

    result = match_job(profile, make_job(required_skills=[], preferred_skills=[]))

    assert result.breakdown.location == 5


@pytest.mark.parametrize(
    ("profile", "job", "decision"),
    [
        (
            make_profile(
                skills={"skills": ["Python", "SQL", "Docker"]},
                target_roles=["Python Engineer"], preferred_locations=["Bengaluru"],
                employment_types=["full_time"],
            ),
            make_job(),
            MatchDecision.STRONG_MATCH,
        ),
        (
            make_profile(skills={"skills": ["Python", "SQL", "Docker"]}, target_roles=["Python Engineer"]),
            make_job(experience_level=ExperienceLevel.MID_LEVEL, employment_type=EmploymentType.CONTRACT,
                     remote_status=RemoteStatus.ONSITE, location="Mumbai, India"),
            MatchDecision.POSSIBLE_MATCH,
        ),
        (
            make_profile(skills={"skills": ["Python"]}),
            make_job(required_skills=["Python", "SQL"], preferred_skills=[]),
            MatchDecision.WEAK_MATCH,
        ),
    ],
)
def test_service_uses_decision_thresholds(profile, job, decision):
    assert JobMatcher().match(profile, job).decision is decision


@pytest.mark.parametrize("profile, job", [(object(), make_job()), (make_profile(), object())])
def test_service_rejects_invalid_inputs(profile, job):
    with pytest.raises(JobValidationError):
        match_job(profile, job)
