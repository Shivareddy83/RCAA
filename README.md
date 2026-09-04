# RCAA

RCAA is a locally runnable payment-operations MVP. It ingests provider-normalized payment records, deterministically reconciles them, preserves evidence, and explains each generated case through a rule-based RCA fallback.

## Run

Copy `.env.example` to `.env`, then run `docker compose up --build`. The backend applies Alembic migrations before starting. API documentation is at `http://localhost:8000/docs`; dashboard is at `http://localhost:3000`. Seed after startup with `python scripts/seed_demo_data.py` (set `DATABASE_URL` to the container-accessible database when run outside Docker).

For local verification: `pip install -r backend/requirements.txt`, `PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head`, `python scripts/seed_demo_data.py`, `uvicorn app.main:app --app-dir backend --reload`, then `pytest -q tests`.

## Design

PostgreSQL is the production/local Compose store; SQLite is supported only for lightweight tests. Money uses `Decimal`. Provider IDs are unique and primary matching keys. Reconciliation is repeatable through case fingerprints and never uses fuzzy financial matching. The Razorpay webhook verifies HMAC-SHA256 and stores each event idempotently. No credentials are committed.

The UI calls the API for summary data, reconciliation runs, case detail, evidence, and deterministic “Ask AI” explanations. The AI endpoint does not manufacture facts: it only returns the persisted RCA/evidence conclusion.

## Limitations and roadmap

Razorpay live fetches are intentionally not invoked without configured test credentials; ingestion is via API/webhook and demo data. Alembic is the migration authority. Application startup does not create or alter the schema. Add authentication/RBAC, async imports, provider polling, richer settlement allocation, and an externally configured AI provider before production use.

## Stage 07 Security

The API now uses JWT bearer authentication, Scrypt password hashing, server-side RBAC, and merchant tenant isolation. Configure `AUTH_SECRET` with a random value of at least 32 characters. Initial registration requires the separate `AUTH_BOOTSTRAP_TOKEN`; later user creation is limited to same-merchant admins. Demo credentials are synthetic and local-only.

## Stage 08 — Audit Logging

Stage 08 adds an append-only, merchant-scoped operational audit trail. Events capture actor, action, resource, request ID, outcome, minimal before/after state, and a SHA-256 hash chain. Audit reads are paginated and role-protected; sensitive credentials are excluded. See `docs/audit-logging.md`.

## Stage 09 — Observability + Operational Monitoring

Stage 09 adds production-oriented operational telemetry without changing financial truth or reconciliation behavior. It provides structured JSON-compatible request logging, safe `X-Request-ID` correlation, Prometheus-compatible `/metrics`, lightweight `/health`, database-backed `/ready`, ingestion/reconciliation/exception/case/AI/audit metrics, safe unexpected-error telemetry, and bounded metric labels. Sensitive credentials, request bodies, AI prompts/responses, and high-cardinality business identifiers are excluded from observability output. See `docs/observability.md`.

## Stage 10 — Reliability + Background Processing

The platform now supports durable background jobs through `POST /api/v1/jobs`, job listing/detail, idempotent creation with `Idempotency-Key`, bounded retries, stale-worker recovery, tenant-scoped job access, worker metrics, and SYSTEM audit events. Run the worker with `python -m app.jobs_worker` from the backend environment.

## Stage 11 — Testing + Security Hardening + Failure Engineering

Stage 11 adds adversarial regression coverage for authentication, JWT handling, RBAC, tenant isolation, financial immutability and precision, reconciliation ambiguity, ingestion/replay safety, audit integrity, background-job ownership/idempotency/concurrency/recovery, retries, AI safety, input validation, pagination, secret handling, SQL/ORM safety, transactions, migrations, and observability security.

The hardening fixes include bounded transaction listing, worker lease-owner validation, ORM-level financial immutability guards, and metric-label allow-listing. See `docs/security-hardening.md` for the threat model, defects, fixes, limitations, and deferred improvements.

## Stage 12 — Production-Quality Operations Console

The existing Next.js frontend was expanded into a role-aware fintech operations console using the existing FastAPI contracts. It adds dashboard, payments, refunds, settlements, exceptions, cases, investigation workspace, jobs, audit, ingestion and reconciliation views, plus centralized authentication/API/error handling and display-only financial formatting.

The frontend does not calculate reconciliation or settlement truth and does not call AI/provider APIs directly. Backend authentication, RBAC and tenant isolation remain authoritative.

Frontend commands: `npm run lint`, `npm run typecheck`, `npm test`, and `npm run build` from `frontend/`.

## Stage 13 — Reproducible Deployment + Production Operations

Stage 13 adds deployment infrastructure around the existing financial domain without changing reconciliation, RCA, AI safety, authentication/RBAC, tenant isolation, or financial calculations.

The deployment shape is intentionally small: PostgreSQL, the FastAPI backend, the existing database-backed worker, and a production Next.js frontend. The backend and worker use the same image; only the backend runs the migration entrypoint. Docker services use health-based startup ordering, a persistent PostgreSQL volume, non-root application users, environment-only secrets, and bounded database/job configuration.

Production configuration is validated at startup. `/health` remains a lightweight liveness endpoint, `/ready` checks database readiness, and `/version` exposes only release/build identifiers. The frontend uses the existing `package-lock.json` and Next standalone output. GitHub Actions runs backend regression, frontend tests, typecheck, source hygiene, production build, Compose configuration validation, and Docker builds.

Backup/restore, deployment rollback, migration safety, disaster recovery assumptions, and incident handling are documented in `docs/deployment.md`, `docs/docker.md`, `docs/ci-cd.md`, `docs/disaster-recovery.md`, and `docs/operations-runbook.md`.

Docker execution was not locally verified in the Stage 13 implementation environment because the Docker CLI is unavailable. No Docker PASS is claimed without that verification.
