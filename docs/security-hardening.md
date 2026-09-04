# RCAA Stage 11 — Security Hardening & Failure Engineering

## Scope

Stage 11 is an adversarial review of the existing Stage 10 backend. No new financial rules or distributed infrastructure were introduced.

## Threat model

The review covered authentication bypass, JWT manipulation, privilege escalation, IDOR, tenant escape, client-controlled merchant ownership, credential leakage, financial mutation, replay, duplicate processing, worker races, job ownership, retries, AI prompt injection/output safety, malformed input, pagination/resource exhaustion, information leakage, SQL/ORM safety, transaction boundaries, constraints, migrations, and observability labels.

## Controls verified

- JWT uses an explicit HS256 allow-list and required claims; expiry, signature, payload modification, inactive-user, and malformed-header attacks are rejected.
- Passwords use Scrypt and user responses do not expose password hashes.
- ADMIN/OPS/ANALYST/VIEWER permissions are enforced server-side.
- Resource lookups are merchant-scoped and client-supplied merchant IDs cannot change authenticated ownership.
- Payment, refund, and settlement source records reject post-creation mutation of financial/source fields at the ORM layer.
- Decimal/Numeric financial values retain exact decimal representation.
- Reconciliation ambiguity remains unresolved rather than selecting an arbitrary candidate.
- Webhook signatures are verified and duplicate event IDs are idempotent.
- Audit records are append-only through ORM mutation hooks and the hash chain detects direct database rewrites.
- Background jobs use tenant-scoped access, idempotency keys, atomic claiming, worker lease ownership, stale-lease recovery, bounded retries, and terminal failure states.
- Job payloads scrub known credential fields before persistence.
- AI investigation remains evidence-grounded, case-scoped, validated, and read-only; unsafe recommended actions are rejected.
- Known API list endpoints use bounded pagination; malformed pagination is rejected with 422.
- Prometheus-compatible metric labels are allow-listed for known metrics; identifiers such as payment ID, case ID, job ID, request ID, merchant ID, and user ID are not accepted as labels.
- Generic application errors return safe messages without stack traces or database details.

## Defects discovered and fixed

### 1. Unbounded transaction listing
**Root cause:** refund and settlement list routes did not apply pagination.

**Fix:** added bounded `page` and `limit` parameters with a maximum of 200 and deterministic ordering.

**Regression:** Stage 11 pagination abuse test.

### 2. Worker execution did not verify lease ownership
**Root cause:** `execute_claimed_job()` accepted a job ID without validating the worker lease owner or lease expiry.

**Fix:** worker execution now accepts the claiming worker ID, verifies ownership and lease freshness, and skips stale/mismatched execution. `run_once()` passes its generated worker ID.

**Regression:** worker ownership and expired-lease tests.

### 3. Financial records could be mutated directly through the ORM
**Root cause:** application-level routes did not expose mutation endpoints, but direct ORM changes to payment/refund/settlement financial fields were still possible.

**Fix:** SQLAlchemy `before_update` guards reject changes to protected financial/source fields after creation.

**Regression:** direct payment/refund/settlement mutation tests.

### 4. Metrics accepted arbitrary labels
**Root cause:** the generic metric helper accepted caller-supplied label names without a metric-specific allow-list.

**Fix:** known metrics now accept only their declared bounded labels.

**Regression:** high-cardinality label attack test.

## Failure engineering

The review exercised duplicate job submission, worker contention, lease ownership, stale-worker recovery, permanent failures, transient retry paths, terminal retry boundaries, AI failure classification, malformed job types, and financial preservation during processing.

## Known limitations

- The job queue remains the Stage 10 database-backed polling worker rather than a distributed queue.
- There is no autoscaling, Kafka, Kubernetes, SIEM, MFA, OAuth/SSO, or notification redesign in this stage.
- Lease renewal for jobs that intentionally run beyond their configured lease remains a deployment/configuration concern; the worker must use a lease long enough for the configured operation timeout.
- Application-level ORM guards do not protect against a privileged operator executing arbitrary SQL; audit hashing is tamper-evident, not a database write-prevention mechanism.
- `RCAA_LEGACY_TEST_AUTH` remains isolated to the test harness and is not a production authentication path. Production requests without a JWT are rejected.

## Deferred improvements

Future security work may include stronger key management, external identity providers, MFA, rate limiting, centralized SIEM integration, and distributed queue infrastructure. These are intentionally outside Stage 11.
