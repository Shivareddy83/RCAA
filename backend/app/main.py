from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from app.api.errors import register_error_handlers
from app.api.middleware import request_context
from app.api.routes import ai, auth, bank, cases, dashboard, reconciliation, transactions, webhooks, users, audit, jobs
from app.core.config import settings, validate_startup_config
from app.observability.logging import configure_structured_logging
from app.observability.metrics import render_prometheus
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import BankTransaction, Case, Evidence, IngestionBatch, Merchant, Payment, RCA, ReconciliationException, Refund, Settlement, WebhookEvent

configure_structured_logging()
validate_startup_config()

app = FastAPI(title="RCAA API", version=settings.rcaa_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(request_context)
register_error_handlers(app)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(reconciliation.router, prefix="/api/v1")
app.include_router(cases.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(bank.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok", "service": "rcaa"}

@app.get("/version")
def version():
    return {"version": settings.rcaa_version, "build_id": settings.build_id, "git_commit_sha": settings.git_commit_sha}

@app.get("/ready")
def ready():
    from sqlalchemy import text
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception:
        return Response(content='{"status":"not_ready","database":"unavailable"}', media_type="application/json", status_code=503)
    finally:
        session.close()

@app.get("/metrics")
def metrics():
    return Response(content=render_prometheus(), media_type="text/plain; version=0.0.4; charset=utf-8")
