"""Deterministic proposal validation and explicit in-memory approval."""

from __future__ import annotations

from datetime import datetime, timezone

from app.jobs.analysis.models import JobAnalysis
from app.jobs.matching.models import MatchResult
from app.jobs.matching.service import JobMatcher
from app.jobs.models import Job
from app.profile.models import CandidateProfile
from app.resume.models import MasterResume
from app.resume.tailoring.models import TailoringProposal
from app.resume.tailoring.service import _known_skills, _resolve_reference
from app.resume.approval.exceptions import ResumeApprovalError, ResumeApprovalRejectedError
from app.resume.approval.models import (
    ApprovedTailoringProposal, ApprovalDecision, ApprovalStatus, ValidationIssue, ValidationResult,
)


class ResumeApprovalValidator:
    """Collect deterministic integrity issues without changing any supplied object."""

    def validate(
        self,
        profile: CandidateProfile,
        resume: MasterResume,
        job: Job,
        match_result: MatchResult,
        job_analysis: JobAnalysis,
        proposal: TailoringProposal,
    ) -> ValidationResult:
        issues: list[ValidationIssue] = []
        snapshots = self._snapshots(profile, resume, job, match_result, job_analysis, proposal)
        if not all(isinstance(value, expected) for value, expected in (
            (profile, CandidateProfile), (resume, MasterResume), (job, Job),
            (match_result, MatchResult), (job_analysis, JobAnalysis), (proposal, TailoringProposal),
        )):
            issues.append(ValidationIssue(code="invalid_proposal", message="All approval inputs must be validated domain models."))
            return ValidationResult(valid=False, issues=issues)

        if proposal.target_job_fingerprint != job.fingerprint:
            issues.append(ValidationIssue(code="target_job_mismatch", message="Proposal target does not match the supplied job."))
        try:
            expected_match = JobMatcher().match(profile, job)
            if match_result != expected_match:
                issues.append(ValidationIssue(code="match_result_mismatch", message="MatchResult does not match the supplied profile and job."))
        except (TypeError, ValueError):
            issues.append(ValidationIssue(code="match_result_mismatch", message="MatchResult could not be verified against the supplied profile and job."))

        if proposal.requires_human_review is not True:
            issues.append(ValidationIssue(code="human_review_required", message="Proposal must require human review."))

        known_skills = _known_skills(profile, resume)
        for skill in proposal.selected_skills:
            if " ".join(skill.casefold().split()) not in known_skills:
                issues.append(ValidationIssue(code="unknown_selected_skill", message=f"Selected skill is not in supplied facts: {skill}."))

        for change in proposal.changes:
            try:
                actual = _resolve_reference(change.source_reference, profile, resume)
            except Exception as error:
                # The resolver only raises controlled ResumeValidationError values.
                issues.append(ValidationIssue(code="invalid_source_reference", message=str(error), source_reference=change.source_reference))
                continue
            if change.original_text != actual:
                issues.append(ValidationIssue(code="source_text_mismatch", message="original_text does not match the referenced source.", source_reference=change.source_reference))

        current = self._snapshots(profile, resume, job, match_result, job_analysis, proposal)
        if current != snapshots:
            issues.append(ValidationIssue(code="input_mutated", message="Approval validation mutated supplied data."))
        return ValidationResult(valid=not issues, issues=issues)

    @staticmethod
    def _snapshots(*values):
        snapshots = []
        for value in values:
            if hasattr(value, "model_dump"):
                snapshots.append(value.model_dump(mode="json"))
            else:
                snapshots.append(repr(value))
        return snapshots


class ResumeApprovalService:
    """Approve or reject proposals in memory after explicit human action."""

    def __init__(self, validator: ResumeApprovalValidator | None = None) -> None:
        self._validator = validator or ResumeApprovalValidator()

    def validate_proposal(self, *args) -> ValidationResult:
        return self._validator.validate(*args)

    def approve_proposal(
        self, profile, resume, job, match_result, job_analysis, proposal,
        reviewer: str, approval_note: str | None = None, approved_at: datetime | None = None,
    ) -> ApprovedTailoringProposal:
        decision = self.validate_proposal(profile, resume, job, match_result, job_analysis, proposal)
        if not decision.valid:
            codes = ", ".join(issue.code for issue in decision.issues)
            raise ResumeApprovalRejectedError(f"Proposal failed deterministic validation: {codes}.")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ResumeApprovalError("A non-empty reviewer identity is required.")
        timestamp = approved_at or datetime.now(timezone.utc)
        return ApprovedTailoringProposal(
            proposal=proposal,
            target_job_fingerprint=job.fingerprint,
            approved_at=timestamp,
            reviewer=reviewer,
            approval_note=approval_note,
        )

    def reject_proposal(
        self, proposal: TailoringProposal, reviewer: str, note: str | None = None,
        reviewed_at: datetime | None = None,
    ) -> ApprovalDecision:
        if not isinstance(proposal, TailoringProposal):
            raise ResumeApprovalError("proposal must be a validated TailoringProposal.")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ResumeApprovalError("A non-empty reviewer identity is required.")
        return ApprovalDecision(
            status=ApprovalStatus.REJECTED,
            reviewed_at=reviewed_at or datetime.now(timezone.utc),
            reviewer=reviewer,
            note=note,
        )
