from __future__ import annotations

import logging
import os
import threading
from time import monotonic, sleep
from uuid import uuid4

from sqlalchemy import select

from app.ai.service import AIServiceError, investigate
from app.api.deps import get_db
from app.audit import record_event
from app.evidence.builder import build_evidence
from app.jobs import Job, JobStatus, retry_delay_seconds
from app.jobs_service import claim_job, is_retryable, recover_stale_jobs
from app.models import Case, ReconciliationException
from app.observability.metrics import inc, observe
from app.reconciliation.engine import run_reconciliation
from app.ingestion import ingest_records
from app.db.session import SessionLocal
from app.core.config import settings, validate_startup_config

logger = logging.getLogger("rcaa.worker")

validate_startup_config()

BASE_BACKOFF = float(os.getenv("JOB_RETRY_BASE_SECONDS", "1"))
MAX_BACKOFF = float(os.getenv("JOB_RETRY_MAX_SECONDS", "30"))
LEASE_SECONDS = int(os.getenv("JOB_LEASE_SECONDS", "60"))


def _audit(job, action, outcome, metadata, *, request_id=None):
    session = SessionLocal()
    try:
        record_event(session, action=action, resource_type="JOB", resource_id=job.job_id, merchant_id=job.merchant_id,
                     actor_user_id=job.created_by, actor_type="SYSTEM", request_id=request_id or job.request_id,
                     outcome=outcome, metadata={"job_type": job.job_type, **metadata})
        session.commit()
    finally:
        session.close()


def _process(session, job: Job) -> dict:
    payload = job.payload_json or {}
    if payload.get("merchant_id") and payload["merchant_id"] != job.merchant_id:
        raise PermissionError("Job merchant scope mismatch")
    jt = job.job_type
    if jt.startswith("INGEST_"):
        mapping = {
            "INGEST_PAYMENTS": "payment", "INGEST_REFUNDS": "refund",
            "INGEST_SETTLEMENTS": "settlement", "INGEST_BANK_TRANSACTIONS": "bank_transaction",
        }
        record_type = mapping[jt]
        records = payload.get("records")
        if not isinstance(records, list): raise ValueError("records must be a list")
        records = [dict(record, merchant_id=job.merchant_id) for record in records]
        result = ingest_records(session, records, source=str(payload.get("source", "background_job")),
                                provider=payload.get("provider"), record_type=record_type, merchant_id=job.merchant_id, commit=False)
        return result
    if jt == "RUN_RECONCILIATION":
        return run_reconciliation(session, return_report=True, merchant_id=job.merchant_id)
    case_id = payload.get("case_id")
    if not case_id: raise ValueError("case_id is required")
    case = session.scalar(select(Case).where(Case.id == case_id, Case.merchant_id == job.merchant_id))
    if not case: raise LookupError("Case not found")
    if jt == "BUILD_EVIDENCE":
        bundle = build_evidence(session, case)
        return {"case_id": case.id, "evidence_ids": [x.id for x in bundle.items], "complete": bundle.complete, "missing": bundle.missing}
    if jt == "GENERATE_DETERMINISTIC_RCA":
        from app.rca.engine import generate_rca
        rca, created = generate_rca(session, case)
        return {"case_id": case.id, "rca_id": rca.id, "created": created, "root_cause_code": rca.root_cause}
    if jt == "AI_INVESTIGATION":
        if not case.rca: raise LookupError("RCA not found")
        question = str(payload.get("question", "")).strip()
        if not question: raise ValueError("question is required")
        result, request_fingerprint = investigate(session, case, question)
        return {"case_id": case.id, "request_fingerprint": request_fingerprint, "result": result.model_dump()}
    raise ValueError("Unsupported job type")


def execute_claimed_job(job_id: str, worker_id: str | None = None) -> str:
    session = SessionLocal()
    started = monotonic()
    job = session.scalar(select(Job).where(Job.job_id == job_id))
    if not job or job.status != JobStatus.RUNNING.value:
        session.close(); return "SKIPPED"
    if worker_id is not None and job.worker_id != worker_id:
        session.close(); return "SKIPPED"
    if worker_id is not None and job.lease_expires_at is not None:
        lease = job.lease_expires_at
        now = __import__("app.core.time", fromlist=["utc_now"]).utc_now()
        if lease.tzinfo is None: lease = lease.replace(tzinfo=now.tzinfo)
        if lease <= now:
            session.close(); return "SKIPPED"
    inc("jobs_started_total", labels={"job_type": job.job_type, "status": JobStatus.RUNNING.value, "failure_category": "none"})
    try:
        result = _process(session, job)
        job.result_json = result if isinstance(result, dict) else {"result": result}
        job.status = JobStatus.SUCCEEDED.value
        job.completed_at = __import__("app.core.time", fromlist=["utc_now"]).utc_now()
        job.last_error_code = None; job.last_error_message_safe = None
        job.worker_id = None; job.lease_expires_at = None
        record_event(session, action="JOB_SUCCEEDED", resource_type="JOB", resource_id=job.job_id, merchant_id=job.merchant_id,
                     actor_user_id=job.created_by, actor_type="SYSTEM", request_id=job.request_id,
                     metadata={"job_type": job.job_type, "attempt": job.attempt_count})
        session.commit()
        inc("jobs_succeeded_total", labels={"job_type": job.job_type, "status": job.status, "failure_category": "none"})
        observe("job_duration_seconds", monotonic() - started, labels={"job_type": job.job_type, "status": job.status})
        logger.info("job_succeeded", extra={"job_id":job.job_id,"job_type":job.job_type,"request_id":job.request_id,"merchant_id":job.merchant_id,"attempt":job.attempt_count,"status":job.status,"duration_ms":round((monotonic()-started)*1000,2)})
        return job.status
    except Exception as exc:
        session.rollback()
        job = session.scalar(select(Job).where(Job.job_id == job_id))
        category, message = __import__("app.jobs_service", fromlist=["_safe_error"])._safe_error(exc)
        retryable = is_retryable(exc)
        if isinstance(exc, (PermissionError, LookupError, ValueError)):
            retryable = False
        if isinstance(exc, AIServiceError):
            retryable = exc.code in {"AI_TIMEOUT", "AI_PROVIDER_UNAVAILABLE", "AI_RATE_LIMIT", "AI_ERROR"}
        if retryable and job.attempt_count < job.max_attempts:
            job.status = JobStatus.RETRYING.value
            job.next_retry_at = __import__("app.jobs", fromlist=["now_plus"]).now_plus(retry_delay_seconds(job.attempt_count, BASE_BACKOFF, MAX_BACKOFF))
            job.last_error_code = category.upper()[:80]
            job.last_error_message_safe = message
            inc("jobs_retried_total", labels={"job_type": job.job_type, "status": job.status, "failure_category": category})
            action = "JOB_RETRIED"
        else:
            job.status = JobStatus.DEAD_LETTERED.value if job.attempt_count >= job.max_attempts else JobStatus.FAILED.value
            job.completed_at = __import__("app.core.time", fromlist=["utc_now"]).utc_now()
            job.last_error_code = category.upper()[:80]
            job.last_error_message_safe = message
            inc("jobs_dead_lettered_total" if job.status == JobStatus.DEAD_LETTERED.value else "jobs_failed_total",
                labels={"job_type": job.job_type, "status": job.status, "failure_category": category})
            action = "JOB_DEAD_LETTERED" if job.status == JobStatus.DEAD_LETTERED.value else "JOB_FAILED"
        job.worker_id = None; job.lease_expires_at = None
        record_event(session, action=action, resource_type="JOB", resource_id=job.job_id, merchant_id=job.merchant_id,
                     actor_user_id=job.created_by, actor_type="SYSTEM", request_id=job.request_id, outcome="FAILURE",
                     metadata={"job_type":job.job_type,"attempt":job.attempt_count,"failure_category":category,"error_code":job.last_error_code})
        session.commit()
        observe("job_duration_seconds", monotonic()-started, labels={"job_type":job.job_type,"status":job.status})
        logger.error("job_failed", extra={"job_id":job.job_id,"job_type":job.job_type,"request_id":job.request_id,"merchant_id":job.merchant_id,"attempt":job.attempt_count,"status":job.status,"duration_ms":round((monotonic()-started)*1000,2),"failure_category":category})
        return job.status
    finally:
        session.close()


def run_once() -> str | None:
    session = SessionLocal()
    worker_id = str(uuid4())
    try:
        recover_stale_jobs(session, stale_before=__import__("app.jobs", fromlist=["now_plus"]).now_plus(-LEASE_SECONDS))
        job = claim_job(session, worker_id=worker_id, lease_seconds=LEASE_SECONDS)
        if not job: return None
        job_id = job.job_id
    finally:
        session.close()
    return execute_claimed_job(job_id, worker_id=worker_id)


def worker_loop(stop_event: threading.Event | None = None, poll_seconds: float = 1.0):
    stop_event = stop_event or threading.Event()
    while not stop_event.is_set():
        status = run_once()
        if status is None: sleep(poll_seconds)


if __name__ == "__main__":
    import signal
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    logger.info("worker_starting")
    worker_loop(stop_event=stop, poll_seconds=float(os.getenv("JOB_POLL_SECONDS", "1")))
    logger.info("worker_stopped")
