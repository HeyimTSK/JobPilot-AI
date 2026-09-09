# JobPilot AI Architecture Specification

## Purpose and boundaries

JobPilot AI will be a modular personal job-application assistant. It will support job organization, compatibility analysis, truthful document tailoring, and human-controlled application assistance. This specification describes the intended architecture; it does not authorize implementation of these capabilities in the current foundation phase.

The system must preserve a clear separation between verified candidate facts, external job data, derived analyses, AI suggestions, generated artifacts, and human approval decisions.

## Planned modules

### 1. Candidate Profile System

Stores verified candidate information as the source of truth. Future profile data may include skills, work experience, education, certifications, preferences, and contact details. All downstream content must be traceable to this verified source.

### 2. Master Resume System

Stores structured resume data separately from generated resume files. Structured data will support validation and truthful tailoring, while file artifacts will be tracked independently.

### 3. Job Discovery System

Supports permitted sources, official company career pages, job alerts, and user-provided URLs. It must respect source terms, authentication, rate limits, CAPTCHAs, and anti-bot controls. Automated LinkedIn scraping and automated LinkedIn application submission are out of scope.

### 4. Job Normalization

Converts different job sources into a common internal job schema. The normalized record should preserve source provenance and capture relevant fields such as role, company, location, description, requirements, URL, and collection time.

### 5. Job Matching Engine

Uses deterministic matching first, with optional AI-assisted analysis. Deterministic rules should provide explainable scores based on verified candidate data and normalized job requirements; optional AI analysis must remain structured and validated.

### 6. AI Provider Layer

Provides a provider-independent interface supporting local or cloud AI. Provider-specific clients must be isolated so that changing providers does not alter core workflows. No AI library is selected in this foundation phase.

### 7. Resume Tailoring Engine

Produces tailored-resume suggestions from a verified profile, structured master resume, and normalized job information. AI may suggest changes but cannot invent facts. Final output must be validated against the candidate profile before a generated artifact is accepted.

### 8. Application Answer Knowledge Base

Stores verified answers for repeated application questions. It should retain answer provenance, scope, review state, and revision history so unsupported or stale answers are not reused.

### 9. Browser Application Assistant

Uses controlled browser automation where appropriate and pauses for human review. It may assist with form entry only within permitted workflows and must never bypass CAPTCHA, authentication, rate limits, or anti-bot protections. Final application submission always requires explicit human approval.

### 10. Application Tracker

Tracks job status, application history, resumes used, dates, and notes. The tracker will provide an auditable workflow record, including human approval events and generated artifacts associated with each application.

## Cross-cutting design principles

- Use Pydantic to validate structured inputs and AI outputs.
- Use SQLite with SQLAlchemy for local persistence when data models are introduced.
- Keep configuration in environment variables and load local development settings with python-dotenv.
- Use standard Python logging with meaningful operational context; do not log sensitive candidate data unnecessarily.
- Keep modules narrowly scoped, testable, and independently evolvable.
- Prefer deterministic, explainable behavior before optional AI assistance.
