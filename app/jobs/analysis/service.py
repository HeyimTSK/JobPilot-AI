"""AI-assisted job analysis built on the deterministic matching result."""

from __future__ import annotations

import json
from typing import Any

from app.ai.exceptions import AIProviderError
from app.ai.models import AIRequest, AIResponse
from app.ai.provider import AIProvider
from app.ai.validation import validate_json_response
from app.jobs.exceptions import JobValidationError
from app.jobs.matching.models import MatchResult
from app.jobs.models import Job
from app.jobs.analysis.models import JobAnalysis
from app.profile.models import CandidateProfile


_BOUNDARY_INSTRUCTIONS = (
    "Candidate facts are authoritative. Do not invent candidate skills, experience, projects, "
    "education, certifications, achievements, employers, dates, or any other facts. "
    "Do not infer unsupported experience as fact. Base strengths and concerns only on supplied "
    "data. Skill gaps must be based on job requirements versus supplied candidate skills and "
    "experience. The deterministic MatchResult score is authoritative; do not change or "
    "recalculate that score. Return ONLY the requested JSON structure."
)


class JobAnalyzer:
    """Generate validated explanatory analysis through a provider-neutral AI interface."""

    def __init__(self, provider: AIProvider) -> None:
        if not isinstance(provider, AIProvider):
            raise JobValidationError("provider must implement the validated AIProvider contract.")
        self._provider = provider

    def analyze(
        self,
        profile: CandidateProfile,
        job: Job,
        match_result: MatchResult,
    ) -> JobAnalysis:
        """Analyze supplied facts without replacing deterministic matching."""
        self._validate_inputs(profile, job, match_result)
        request = AIRequest(
            system_instruction=_BOUNDARY_INSTRUCTIONS,
            prompt=self._build_prompt(profile, job, match_result),
            metadata={"component": "job_analysis"},
        )
        response = self._provider.generate(request)
        if not isinstance(response, AIResponse):
            raise AIProviderError("AI provider returned an invalid response object.")
        return validate_json_response(response, JobAnalysis)

    @staticmethod
    def _validate_inputs(
        profile: CandidateProfile,
        job: Job,
        match_result: MatchResult,
    ) -> None:
        if not isinstance(profile, CandidateProfile):
            raise JobValidationError("profile must be a validated CandidateProfile.")
        if not isinstance(job, Job):
            raise JobValidationError("job must be a validated Job.")
        if not isinstance(match_result, MatchResult):
            raise JobValidationError("match_result must be a validated MatchResult.")

    @staticmethod
    def _build_prompt(
        profile: CandidateProfile,
        job: Job,
        match_result: MatchResult,
    ) -> str:
        """Build stable JSON context while excluding contact and salary secrets."""
        candidate_context: dict[str, Any] = {
            "current_title": profile.current_title,
            "professional_summary": profile.professional_summary,
            "years_of_experience": profile.years_of_experience,
            "skills": profile.skills,
            "experience": [
                {
                    "company": item.company,
                    "role": item.role,
                    "start_date": item.start_date,
                    "end_date": item.end_date,
                    "is_current": item.is_current,
                    "responsibilities": item.responsibilities,
                    "achievements": item.achievements,
                    "technologies": item.technologies,
                }
                for item in profile.experience
            ],
            "education": [item.model_dump() for item in profile.education],
            "projects": [item.model_dump(exclude={"repository_url", "live_url"}) for item in profile.projects],
            "certifications": [item.model_dump(exclude={"credential_url"}) for item in profile.certifications],
        }
        job_context = {
            "job_title": job.job_title,
            "company_name": job.company_name,
            "location": job.location,
            "remote_status": job.remote_status.value,
            "employment_type": job.employment_type.value,
            "experience_level": job.experience_level.value,
            "description": job.description,
            "required_skills": job.required_skills,
            "preferred_skills": job.preferred_skills,
        }
        match_context = match_result.model_dump(mode="json")
        return (
            "Analyze this normalized job against the verified candidate profile. "
            "Provide role_summary, strengths, concerns, skill_gaps, relevant_experience, "
            "recommendation, and confidence as JSON matching the requested schema.\n\n"
            f"{_BOUNDARY_INSTRUCTIONS}\n\n"
            f"VERIFIED_CANDIDATE_PROFILE:\n{json.dumps(candidate_context, sort_keys=True)}\n\n"
            f"NORMALIZED_JOB:\n{json.dumps(job_context, sort_keys=True)}\n\n"
            f"DETERMINISTIC_MATCH_RESULT (authoritative score):\n{json.dumps(match_context, sort_keys=True)}"
        )


def analyze_job(
    profile: CandidateProfile,
    job: Job,
    match_result: MatchResult,
    provider: AIProvider,
) -> JobAnalysis:
    """Convenience entry point for provider-neutral job analysis."""
    return JobAnalyzer(provider).analyze(profile, job, match_result)
