# AGENTS.md

## Project goal
Build a research prototype for a personalized tutoring chatbot that:
1. accepts a learner question,
2. retrieves relevant learning materials with RAG,
3. reads a per-user skill profile,
4. generates multiple answer candidates,
5. lets the learner choose the best answer,
6. stores both chosen and non-chosen candidates,
7. updates the learner-specific skill rules from the feedback,
8. uses the updated skill rules in future generations.

## Non-negotiable constraints
- Development environment MUST be Docker-based.
- The whole system MUST run locally with `docker compose up --build`.
- Use a monorepo structure.
- Backend: Python 3.12 + FastAPI.
- Frontend: Next.js + TypeScript.
- Database: PostgreSQL 16 + pgvector.
- Background worker: Python worker service in a separate container.
- LLM provider abstraction is required.
- Default LLM provider is Gemini, but implementation must allow future provider replacement.
- All environment variables must be loaded from `.env`.
- Do not hardcode secrets.
- Write tests for critical paths.
- Prefer simple and explicit implementations over clever abstractions.

## Build order
1. Create monorepo skeleton.
2. Create Dockerfiles and docker-compose.yml.
3. Create backend health check, settings, DB connection, migrations.
4. Create frontend basic pages.
5. Implement RAG ingestion and retrieval.
6. Implement answer generation API with multiple candidates.
7. Implement answer selection and feedback persistence.
8. Implement skill updater.
9. Implement experiment mode (skills ON/OFF).
10. Add tests, fixtures, seed data, documentation.

## Coding rules
- Keep functions short and testable.
- Use typed schemas everywhere.
- Use Pydantic models for API IO.
- Use SQLAlchemy 2.x style.
- Use Alembic migrations.
- Use structured JSON outputs from the LLM for machine-readable responses.
- Avoid hidden side effects.
- Log important state transitions.
- Add clear TODO comments only when absolutely necessary.

## Deliverables
When implementing, produce:
- working source code,
- Docker setup,
- migrations,
- API docs,
- tests,
- seed scripts,
- sample data,
- README with run instructions.

## Definition of done
The implementation is complete only if:
- `docker compose up --build` starts all services,
- a sample document can be ingested,
- a learner can ask a question,
- three answer candidates are returned,
- a learner can choose one answer and optionally rate it,
- the system stores chosen and non-chosen candidates,
- the skill updater modifies the skill rules,
- later generations reflect the stored rules,
- experiment mode can compare skills enabled vs disabled,
- critical backend tests pass.
