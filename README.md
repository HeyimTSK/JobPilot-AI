# JobPilot AI

JobPilot AI is a modular, personal job-application assistant. It is being designed to help a candidate organize verified profile data, evaluate opportunities, produce truthful tailored materials, assist with applications, and maintain an application history—while keeping the candidate in control of every submission.

> This repository currently contains the project foundation and documentation only. It does not yet collect jobs, automate browsers, call AI providers, generate resumes, or submit applications.

## Planned features

- Verified candidate profile and master-resume data management
- Job intake from permitted sources and user-provided URLs
- Common job schema and deterministic compatibility scoring
- Optional, provider-independent AI assistance with validation safeguards
- Truthful resume-tailoring workflow based only on verified information
- Reusable, verified application-answer knowledge base
- Controlled browser assistance that pauses for human review
- Application status, history, notes, and artifact tracking

## Technology stack

- Python 3.12+
- SQLite and SQLAlchemy
- Pydantic validation
- Playwright for future controlled browser automation
- Pytest and pytest-cov
- python-dotenv
- Standard Python logging

## Project structure

```text
JobPilot-AI/
├── app/                 # Future modular application packages
│   ├── core/            # Shared configuration, logging, and infrastructure
│   ├── profile/         # Verified candidate profile
│   ├── jobs/            # Job intake, normalization, and matching
│   ├── ai/              # Provider-independent AI integration
│   ├── resume/          # Master resume and tailoring workflows
│   ├── applications/    # Application answers and tracking
│   └── automation/      # Controlled browser assistance
├── data/                # Local SQLite database and non-committed data
├── resumes/
│   ├── master/          # Master-resume files (handling policy pending)
│   └── generated/       # Generated resumes (ignored by Git)
├── tests/               # Future test suite
├── logs/                # Runtime logs (ignored by Git)
└── screenshots/         # Automation screenshots (ignored by Git)
```

## Safety principles

- Candidate facts are verified before use; the system must never invent qualifications or achievements.
- AI output is advisory until structured and validated against verified data.
- AI providers remain interchangeable behind a provider-independent interface.
- Applications require explicit human review and approval before final submission.
- The project will not bypass CAPTCHAs, authentication, rate limits, or anti-bot systems, and will not use stealth or detection-evasion techniques.
- LinkedIn will not be used for automated scraping or automated application submission.

## Development roadmap

1. Establish data schemas, configuration, logging, and tests.
2. Build the verified candidate profile and structured master-resume systems.
3. Add permitted job intake, normalization, and deterministic matching.
4. Add a validated, provider-independent AI layer and resume-tailoring workflow.
5. Add a verified answer knowledge base and application tracker.
6. Add controlled browser assistance with required human review gates.

See [PROJECT_SPEC.md](PROJECT_SPEC.md) for the planned architecture and [PROJECT_RULES.md](PROJECT_RULES.md) for binding development rules.
