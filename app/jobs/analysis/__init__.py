"""AI-assisted, structured analysis layered on deterministic job matching."""

from app.jobs.analysis.models import JobAnalysis, JobRecommendation
from app.jobs.analysis.service import JobAnalyzer, analyze_job

__all__ = ["JobAnalysis", "JobAnalyzer", "JobRecommendation", "analyze_job"]
