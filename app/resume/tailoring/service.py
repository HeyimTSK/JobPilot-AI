"""Deterministic validation around provider-neutral resume tailoring proposals."""

from __future__ import annotations

import json
import re
from typing import Any

from app.ai.exceptions import AIProviderError
from app.ai.models import AIRequest, AIResponse
from app.ai.provider import AIProvider
from app.ai.validation import validate_json_response
from app.jobs.analysis.models import JobAnalysis
from app.jobs.exceptions import JobValidationError
from app.jobs.matching.models import MatchResult
from app.jobs.matching.service import JobMatcher
from app.jobs.models import Job
from app.profile.models import CandidateProfile
from app.resume.exceptions import ResumeValidationError
from app.resume.models import MasterResume
from app.resume.tailoring.models import (
    ResumeSourceReference,
    ResumeSourceType,
    TailoringAction,
    TailoringProposal,
)


_INSTRUCTIONS = (
    "Candidate facts are authoritative. CandidateProfile is the authoritative source of verified facts. MasterResume is a "
    "presentation of supplied facts. Do not invent facts. Do not invent skills, technologies, employers, dates, "
    "titles, education, certifications, achievements, metrics, responsibilities, outcomes, "
    "years of experience, or qualifications. Every proposed change must reference supplied "
    "source material. Do not change the deterministic match score. Do not treat AI-generated "
    "statements as verified candidate facts. This output is a proposal requiring human review. "
    "Return only the requested JSON."
)


class ResumeTailoringService:
    """Request and deterministically validate a human-reviewed tailoring proposal."""

    def __init__(self, provider: AIProvider) -> None:
        if not isinstance(provider, AIProvider):
            raise ResumeValidationError("provider must implement the AIProvider contract.")
        self._provider = provider

    def propose(
        self,
        profile: CandidateProfile,
        resume: MasterResume,
        job: Job,
        match_result: MatchResult,
        job_analysis: JobAnalysis,
    ) -> TailoringProposal:
        self._validate_inputs(profile, resume, job, match_result, job_analysis)
        expected_match = JobMatcher().match(profile, job)
        if match_result != expected_match:
            raise ResumeValidationError("MatchResult does not match the supplied profile and job.")

        response = self._provider.generate(AIRequest(
            system_instruction=_INSTRUCTIONS,
            prompt=self._build_prompt(profile, resume, job, match_result, job_analysis),
            metadata={"component": "resume_tailoring"},
        ))
        if not isinstance(response, AIResponse):
            raise AIProviderError("AI provider returned an invalid response object.")
        proposal = validate_json_response(response, TailoringProposal)
        return validate_tailoring_proposal(proposal, profile, resume, job)

    @staticmethod
    def _validate_inputs(profile, resume, job, match_result, job_analysis) -> None:
        if not isinstance(profile, CandidateProfile):
            raise ResumeValidationError("profile must be a validated CandidateProfile.")
        if not isinstance(resume, MasterResume):
            raise ResumeValidationError("resume must be a validated MasterResume.")
        if not isinstance(job, Job):
            raise JobValidationError("job must be a validated Job.")
        if not isinstance(match_result, MatchResult):
            raise ResumeValidationError("match_result must be a validated MatchResult.")
        if not isinstance(job_analysis, JobAnalysis):
            raise ResumeValidationError("job_analysis must be a validated JobAnalysis.")

    @staticmethod
    def _build_prompt(profile, resume, job, match_result, job_analysis) -> str:
        profile_context = {
            "current_title": profile.current_title,
            "professional_summary": profile.professional_summary,
            "years_of_experience": profile.years_of_experience,
            "skills": profile.skills,
            "experience": [item.model_dump() for item in profile.experience],
            "education": [item.model_dump() for item in profile.education],
            "projects": [item.model_dump(exclude={"repository_url", "live_url"}) for item in profile.projects],
            "certifications": [item.model_dump(exclude={"credential_url"}) for item in profile.certifications],
        }
        resume_context = resume.model_dump(mode="json", exclude={"contact"})
        job_context = {
            "fingerprint": job.fingerprint,
            "job_title": job.job_title,
            "company_name": job.company_name,
            "location": job.location,
            "description": job.description,
            "required_skills": job.required_skills,
            "preferred_skills": job.preferred_skills,
            "remote_status": job.remote_status.value,
            "employment_type": job.employment_type.value,
            "experience_level": job.experience_level.value,
        }
        return (
            "Create a structured TailoringProposal for this job. Include source_type profile or "
            "resume and explicit source_path references for every change. Keep requires_human_review true.\n\n"
            f"{_INSTRUCTIONS}\n\nPROFILE:\n{json.dumps(profile_context, sort_keys=True, default=str)}\n\n"
            f"MASTER_RESUME:\n{json.dumps(resume_context, sort_keys=True, default=str)}\n\n"
            f"JOB:\n{json.dumps(job_context, sort_keys=True, default=str)}\n\n"
            f"MATCH_RESULT (authoritative; do not recalculate):\n{json.dumps(match_result.model_dump(mode='json'), sort_keys=True)}\n\n"
            f"JOB_ANALYSIS:\n{json.dumps(job_analysis.model_dump(mode='json'), sort_keys=True)}"
        )


def _resolve_reference(reference: ResumeSourceReference, profile: CandidateProfile, resume: MasterResume) -> str:
    """Resolve only explicit supported paths; never evaluate arbitrary expressions."""
    path = reference.source_path
    root = profile if reference.source_type == ResumeSourceType.PROFILE else resume
    if path.startswith("profile.") and reference.source_type != ResumeSourceType.PROFILE:
        raise ResumeValidationError("source reference root does not match source_type")
    if path.startswith("resume.") and reference.source_type != ResumeSourceType.RESUME:
        raise ResumeValidationError("source reference root does not match source_type")
    prefix = "profile." if reference.source_type == ResumeSourceType.PROFILE else "resume."
    if not path.startswith(prefix):
        raise ResumeValidationError("source reference path must match its source_type")
    relative = path[len(prefix):]

    skills_match = re.fullmatch(r"skills\[([^\]]+)\]\[(\d+)\]", relative)
    if skills_match:
        category, index = skills_match.group(1), int(skills_match.group(2))
        skills = root.skills.get(category) if hasattr(root, "skills") else None
        if skills is None or index >= len(skills):
            raise ResumeValidationError(f"source reference does not exist: {path}")
        return skills[index]

    if relative.startswith("skills[") and relative.endswith("]") and hasattr(root, "skills"):
        index = int(relative[7:-1])
        flattened = [value for values in root.skills.values() for value in values]
        if index >= len(flattened):
            raise ResumeValidationError(f"source reference does not exist: {path}")
        return flattened[index]

    match = re.fullmatch(r"(experience|projects)\[(\d+)\]\.(bullets|technologies|responsibilities|achievements|description)\[(\d+)\]", relative)
    if match:
        collection, item_index, field, value_index = match.groups()
        items = getattr(root, collection, [])
        item = items[int(item_index)] if int(item_index) < len(items) else None
        values = getattr(item, field, None) if item is not None else None
        if not isinstance(values, list) or int(value_index) >= len(values):
            raise ResumeValidationError(f"source reference does not exist: {path}")
        return values[int(value_index)]

    match = re.fullmatch(r"(experience|projects)\[(\d+)\]\.(description|role|company|name)", relative)
    if match:
        collection, item_index, field = match.groups()
        items = getattr(root, collection, [])
        if int(item_index) >= len(items):
            raise ResumeValidationError(f"source reference does not exist: {path}")
        value = getattr(items[int(item_index)], field, None)
        if not isinstance(value, str):
            raise ResumeValidationError(f"source reference does not exist: {path}")
        return value

    raise ResumeValidationError(f"unsupported source reference: {path}")


def _known_skills(profile: CandidateProfile, resume: MasterResume) -> set[str]:
    values = [skill for skills in profile.skills.values() for skill in skills]
    values.extend(skill for item in profile.experience for skill in item.technologies)
    values.extend(skill for item in profile.projects for skill in item.technologies)
    values.extend(skill for skills in resume.skills.values() for skill in skills)
    values.extend(skill for item in resume.experience for skill in item.technologies)
    values.extend(skill for item in resume.projects for skill in item.technologies)
    return {" ".join(value.casefold().split()) for value in values}


def validate_tailoring_proposal(proposal, profile, resume, job) -> TailoringProposal:
    if not isinstance(proposal, TailoringProposal):
        raise ResumeValidationError("proposal must be a validated TailoringProposal.")
    if proposal.target_job_fingerprint != job.fingerprint:
        raise ResumeValidationError("tailoring proposal targets a different job.")
    if proposal.requires_human_review is not True:
        raise ResumeValidationError("tailoring proposals always require human review.")
    known = _known_skills(profile, resume)
    for skill in proposal.selected_skills:
        if " ".join(skill.casefold().split()) not in known:
            raise ResumeValidationError(f"selected skill is not present in supplied facts: {skill}")
    for change in proposal.changes:
        actual = _resolve_reference(change.source_reference, profile, resume)
        if change.original_text != actual:
            raise ResumeValidationError(
                f"original_text does not match source reference: {change.source_reference.source_path}"
            )
        if change.action == TailoringAction.REMOVE and change.proposed_text is not None:
            raise ResumeValidationError("remove changes cannot contain proposed_text")
    return proposal


def tailor_resume(profile, resume, job, match_result, job_analysis, provider) -> TailoringProposal:
    return ResumeTailoringService(provider).propose(profile, resume, job, match_result, job_analysis)
