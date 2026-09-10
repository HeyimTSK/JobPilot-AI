"""Deterministic, explainable matching of verified candidates to jobs."""

from __future__ import annotations

from app.jobs.exceptions import JobValidationError
from app.jobs.matching.models import MatchDecision, MatchResult, MatchScoreBreakdown
from app.jobs.models import EmploymentType, ExperienceLevel, Job, RemoteStatus
from app.profile.models import CandidateProfile


def _normalize_text(value: str) -> str:
    """Normalize text for the deliberately conservative comparisons in this module."""
    return " ".join(value.casefold().split())


def _candidate_skills(profile: CandidateProfile) -> set[str]:
    """Return all verified profile skills, preserving no unverified inferences."""
    values = [skill for skills in profile.skills.values() for skill in skills]
    values.extend(skill for experience in profile.experience for skill in experience.technologies)
    values.extend(skill for project in profile.projects for skill in project.technologies)
    return {_normalize_text(value) for value in values if _normalize_text(value)}


def _enum_preference(
    value: str | None,
    enum_type: type[ExperienceLevel] | type[EmploymentType],
    aliases: dict[str, ExperienceLevel | EmploymentType],
) -> ExperienceLevel | EmploymentType | None:
    """Map an explicit profile preference to an existing job enum value."""
    if value is None:
        return None
    normalized = _normalize_text(value)
    for member in enum_type:
        if normalized == _normalize_text(member.value):
            return member
    return aliases.get(normalized)


_EXPERIENCE_ALIASES: dict[str, ExperienceLevel] = {
    "intern": ExperienceLevel.INTERNSHIP,
    "entry level": ExperienceLevel.ENTRY_LEVEL,
    "entry-level": ExperienceLevel.ENTRY_LEVEL,
    "junior": ExperienceLevel.ENTRY_LEVEL,
    "jr": ExperienceLevel.ENTRY_LEVEL,
    "mid level": ExperienceLevel.MID_LEVEL,
    "mid-level": ExperienceLevel.MID_LEVEL,
    "mid": ExperienceLevel.MID_LEVEL,
    "senior": ExperienceLevel.SENIOR,
    "sr": ExperienceLevel.SENIOR,
}

_EMPLOYMENT_ALIASES: dict[str, EmploymentType] = {
    "full time": EmploymentType.FULL_TIME,
    "full-time": EmploymentType.FULL_TIME,
    "part time": EmploymentType.PART_TIME,
    "part-time": EmploymentType.PART_TIME,
    "contractor": EmploymentType.CONTRACT,
    "temp": EmploymentType.TEMPORARY,
    "intern": EmploymentType.INTERNSHIP,
    "apprentice": EmploymentType.APPRENTICESHIP,
}

_REMOTE_PREFERENCES: dict[str, set[RemoteStatus]] = {
    "remote": {RemoteStatus.REMOTE},
    "fully remote": {RemoteStatus.REMOTE},
    "hybrid": {RemoteStatus.HYBRID},
    "onsite": {RemoteStatus.ONSITE},
    "on site": {RemoteStatus.ONSITE},
    "on-site": {RemoteStatus.ONSITE},
    "remote or hybrid": {RemoteStatus.REMOTE, RemoteStatus.HYBRID},
    "remote/hybrid": {RemoteStatus.REMOTE, RemoteStatus.HYBRID},
    "remote or onsite": {RemoteStatus.REMOTE, RemoteStatus.ONSITE},
    "hybrid or onsite": {RemoteStatus.HYBRID, RemoteStatus.ONSITE},
}


class JobMatcher:
    """Score a validated candidate profile against one validated normalized job."""

    def match(self, profile: CandidateProfile, job: Job) -> MatchResult:
        """Produce a reproducible result without using salary or inferred candidate data."""
        if not isinstance(profile, CandidateProfile):
            raise JobValidationError("profile must be a validated CandidateProfile.")
        if not isinstance(job, Job):
            raise JobValidationError("job must be a validated Job.")

        reasons: list[str] = []
        warnings: list[str] = []
        verified_skills = _candidate_skills(profile)
        matched_required = self._matched_skills(job.required_skills, verified_skills)
        missing_required = [
            skill for skill in job.required_skills if _normalize_text(skill) not in verified_skills
        ]
        matched_preferred = self._matched_skills(job.preferred_skills, verified_skills)

        required_score = self._proportional_score(job.required_skills, matched_required, 40)
        preferred_score = self._proportional_score(job.preferred_skills, matched_preferred, 10)
        if job.required_skills:
            reasons.append(
                f"Matched {len(matched_required)} of {len(job.required_skills)} required skills."
            )
        if missing_required:
            warnings.append(
                "Required skills not found in the verified profile: "
                + ", ".join(missing_required)
                + "."
            )
        if job.preferred_skills and matched_preferred:
            reasons.append(
                f"Matched {len(matched_preferred)} preferred skills."
            )

        role_score = self._role_score(profile, job, reasons, warnings)
        experience_score = self._experience_score(profile, job, reasons, warnings)
        employment_score = self._employment_score(profile, job, reasons, warnings)
        remote_score = self._remote_score(profile, job, reasons, warnings)
        location_score = self._location_score(profile, job, reasons, warnings)
        breakdown = MatchScoreBreakdown(
            required_skills=required_score,
            target_role=role_score,
            preferred_skills=preferred_score,
            experience_level=experience_score,
            employment_type=employment_score,
            remote_preference=remote_score,
            location=location_score,
        )
        score = breakdown.total
        decision = (
            MatchDecision.STRONG_MATCH if score >= 80 else
            MatchDecision.POSSIBLE_MATCH if score >= 60 else
            MatchDecision.WEAK_MATCH
        )
        return MatchResult(
            score=score, decision=decision, breakdown=breakdown,
            matched_required_skills=matched_required,
            missing_required_skills=missing_required,
            matched_preferred_skills=matched_preferred,
            reasons=reasons, warnings=warnings,
        )

    @staticmethod
    def _matched_skills(job_skills: list[str], verified_skills: set[str]) -> list[str]:
        return [skill for skill in job_skills if _normalize_text(skill) in verified_skills]

    @staticmethod
    def _proportional_score(job_skills: list[str], matched: list[str], maximum: int) -> float:
        return round(maximum * len(matched) / len(job_skills), 2) if job_skills else 0

    @staticmethod
    def _role_score(profile: CandidateProfile, job: Job, reasons: list[str], warnings: list[str]) -> int:
        preferences = profile.job_preferences
        if not preferences or not preferences.target_roles:
            warnings.append("No target-role preference is available in the verified profile.")
            return 0
        title = _normalize_text(job.job_title)
        if any(
            (role := _normalize_text(target_role)) and (role in title or title in role)
            for target_role in preferences.target_roles
        ):
            reasons.append("Job title matches a verified target-role preference.")
            return 15
        return 0

    @staticmethod
    def _experience_score(profile: CandidateProfile, job: Job, reasons: list[str], warnings: list[str]) -> int:
        preference = profile.job_preferences.experience_level if profile.job_preferences else None
        level = _enum_preference(preference, ExperienceLevel, _EXPERIENCE_ALIASES)
        if preference is not None and level is None:
            warnings.append("Experience-level preference is not recognized for matching.")
        if level == job.experience_level:
            reasons.append("Job experience level matches the verified preference.")
            return 10
        return 0

    @staticmethod
    def _employment_score(profile: CandidateProfile, job: Job, reasons: list[str], warnings: list[str]) -> int:
        preferences = profile.job_preferences.employment_types if profile.job_preferences else []
        levels = [_enum_preference(value, EmploymentType, _EMPLOYMENT_ALIASES) for value in preferences]
        if preferences and not any(levels):
            warnings.append("Employment-type preferences are not recognized for matching.")
        if job.employment_type in levels:
            reasons.append("Job employment type matches a verified preference.")
            return 10
        return 0

    @staticmethod
    def _remote_score(profile: CandidateProfile, job: Job, reasons: list[str], warnings: list[str]) -> int:
        preference = profile.job_preferences.remote_preference if profile.job_preferences else None
        statuses = _REMOTE_PREFERENCES.get(_normalize_text(preference)) if preference else None
        if preference is not None and statuses is None:
            warnings.append("Remote-work preference is not recognized for matching.")
        if statuses and job.remote_status in statuses:
            reasons.append("Job work arrangement matches the verified remote preference.")
            return 10
        return 0

    @staticmethod
    def _location_score(profile: CandidateProfile, job: Job, reasons: list[str], warnings: list[str]) -> int:
        preferences = profile.job_preferences.preferred_locations if profile.job_preferences else []
        job_location = _normalize_text(job.location)
        if not preferences:
            warnings.append("No preferred-location preference is available in the verified profile.")
            return 0
        if any(
            (location := _normalize_text(preferred_location))
            and (location in job_location or job_location in location)
            for preferred_location in preferences
        ):
            reasons.append("Job location matches a verified preferred location.")
            return 5
        return 0


def match_job(profile: CandidateProfile, job: Job) -> MatchResult:
    """Convenience entry point for deterministic candidate-to-job matching."""
    return JobMatcher().match(profile, job)
