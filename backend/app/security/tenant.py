from __future__ import annotations
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import BankTransaction, Case, Evidence, Payment, RCA, ReconciliationException, Refund, Settlement, IngestionBatch

def scoped(model, session: Session, record_id: str, user):
    if not hasattr(model, 'merchant_id'):
        if model in (Evidence, RCA):
            case_id_col = Evidence.reconciliation_case_id if model is Evidence else RCA.reconciliation_case_id
            case = session.scalar(select(Case).where(Case.id == case_id_col, Case.merchant_id == user.merchant_id))
            if not case: raise HTTPException(404, "Resource not found")
            value = session.get(model, record_id)
        else:
            value = session.get(model, record_id)
    else:
        value = session.scalar(select(model).where(model.id == record_id, model.merchant_id == user.merchant_id))
    if not value: raise HTTPException(404, "Resource not found")
    return value

def ensure_merchant(value: str | None, user):
    if value and value != user.merchant_id:
        raise HTTPException(404, "Resource not found")
    return user.merchant_id
