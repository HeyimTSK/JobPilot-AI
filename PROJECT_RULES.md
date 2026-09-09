# JobPilot AI Development Rules

These rules apply to all future development in this repository.

1. Build modular components with clear responsibilities.
2. Never modify unrelated files.
3. Do not introduce dependencies without justification.
4. Candidate data must always be validated.
5. AI output must be structured and validated before use.
6. AI providers must be interchangeable.
7. Human approval is required before application submission.
8. Never bypass CAPTCHA, authentication, rate limits, or anti-bot systems.
9. Never implement stealth or detection-evasion mechanisms.
10. LinkedIn must not be used for automated scraping or automated application submission.
11. Every important module must eventually have tests.
12. Errors must be logged with useful context.
13. Sensitive candidate data must not be committed to Git.
14. Configuration secrets must only exist in environment variables.
15. Prefer simple solutions over unnecessary architecture.
16. Do not refactor stable modules unless required.
