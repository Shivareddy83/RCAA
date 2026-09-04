from __future__ import annotations
from datetime import datetime
from uuid import uuid4
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.time import utc_now
from app.models import Case, CaseExceptionLink, CaseEvent, CaseNote, ReconciliationException
from .models import CaseStatus, CasePriority, ResolutionCode, VALID_TRANSITIONS

class CaseBusinessError(ValueError):
    pass


def next_case_number(session: Session) -> str:
    # Operational identifier is human-readable; the unique DB constraint is the final guard.
    year = utc_now().year
    count = session.scalar(select(func.count(Case.id)).where(Case.case_number.like(f"RCAA-{year}-%"))) or 0
    return f"RCAA-{year}-{count + 1:06d}"


def add_case_event(session, case, event_type, actor_reference=None, metadata=None):
    session.add(CaseEvent(id=uuid4().hex, case_id=case.id, event_type=event_type,
                          actor_reference=actor_reference, metadata_json=metadata or {}, created_at=utc_now()))


def _resolve_merchant(case, exception=None):
    if exception and exception.merchant_id:
        return exception.merchant_id
    return (case.metadata_json or {}).get("merchant_id")


def create_case(session: Session, *, exception_id: str | None = None, merchant_id: str | None = None,
                title: str | None = None, description: str | None = None,
                priority: str | None = None, assigned_to: str | None = None,
                actor_reference: str | None = None):
    exception = session.get(ReconciliationException, exception_id) if exception_id else None
    if exception_id and not exception:
        raise CaseBusinessError("Exception not found")
    if exception and exception.reconciliation_case_id:
        existing = session.get(Case, exception.reconciliation_case_id)
        if existing:
            return existing, False
    if priority and priority.upper() not in {x.value for x in CasePriority}:
        raise CaseBusinessError("Invalid priority")
    case = Case(
        id=uuid4().hex, case_number=next_case_number(session),
        merchant_id=merchant_id or (exception.merchant_id if exception else None),
        payment_id=None, record_id=exception.primary_record_id if exception else None,
        record_type="exception" if exception else "case",
        case_type=exception.exception_code if exception else "OPERATIONAL",
        severity=exception.severity if exception else (priority or CasePriority.MEDIUM.value),
        status=CaseStatus.OPEN.value,
        priority=(priority or (exception.severity if exception else CasePriority.MEDIUM.value)).upper(),
        assigned_to=(assigned_to.strip() if assigned_to else None),
        title=title or (f"Investigate {exception.exception_code}" if exception else "RCAA operational case"),
        description=description or (f"Operational investigation for exception {exception.exception_code}." if exception else ""),
        expected_amount=exception.expected_amount if exception else 0,
        actual_amount=exception.actual_amount if exception else 0,
        difference=exception.difference if exception else 0,
        confidence=0,
        match_method="NONE", match_confidence="NONE", matched_record_id=exception.related_record_id if exception else None,
        reason_code=exception.exception_code if exception else "UNKNOWN",
        summary=exception.exception_code if exception else "Operational case",
        metadata_json={"merchant_id": merchant_id or (exception.merchant_id if exception else None)} if (merchant_id or (exception.merchant_id if exception else None)) else {},
        fingerprint=(exception.fingerprint if exception else f"manual:{uuid4().hex}"),
        created_at=utc_now(), resolved_at=None,
    )
    session.add(case); session.flush()
    add_case_event(session, case, "CASE_CREATED", actor_reference)
    if exception:
        session.add(CaseExceptionLink(case_id=case.id, exception_id=exception.id))
        add_case_event(session, case, "EXCEPTION_ATTACHED", actor_reference, {"exception_id": exception.id})
        exception.reconciliation_case_id = case.id
        # Stage 05: build deterministic evidence and RCA from stored records only.
        from app.rca.engine import generate_rca
        generate_rca(session, case, exception)
    if assigned_to:
        add_case_event(session, case, "CASE_ASSIGNED", actor_reference, {"assigned_to": assigned_to.strip()})
    try:
        session.commit(); session.refresh(case)
    except IntegrityError:
        session.rollback()
        if exception:
            existing = session.scalar(select(Case).where(Case.fingerprint == exception.fingerprint))
            if existing:
                return existing, False
        raise CaseBusinessError("Case creation conflicted with an existing case")
    return case, True


def get_case(session, case_id):
    return session.get(Case, case_id)


def transition(session, case, target: str, actor_reference=None, resolution_code=None, resolution_note=None):
    try: target_status = CaseStatus(target.upper())
    except ValueError: raise CaseBusinessError("Invalid case status")
    current = CaseStatus(case.status)
    if target_status not in VALID_TRANSITIONS[current]:
        raise CaseBusinessError(f"Invalid case status transition: {current.value} -> {target_status.value}")
    if target_status == CaseStatus.RESOLVED:
        if not resolution_code:
            raise CaseBusinessError("resolution_code is required to resolve a case")
        try: code = ResolutionCode(resolution_code.upper()).value
        except ValueError: raise CaseBusinessError("Invalid resolution_code")
        case.resolution_code = code
        case.resolution_note = resolution_note
        case.resolved_at = utc_now()
        add_case_event(session, case, "CASE_RESOLVED", actor_reference, {"resolution_code": code})
    elif target_status == CaseStatus.REOPENED:
        case.resolved_at = None
        add_case_event(session, case, "CASE_REOPENED", actor_reference)
    else:
        add_case_event(session, case, "CASE_STATUS_CHANGED", actor_reference, {"from": current.value, "to": target_status.value})
    case.status = target_status.value
    case.updated_at = utc_now()
    session.commit(); session.refresh(case)
    return case


def assign_case(session, case, assigned_to: str | None, actor_reference=None):
    value = assigned_to.strip() if assigned_to else None
    if assigned_to is not None and not value:
        raise CaseBusinessError("assigned_to must be a non-empty identifier")
    case.assigned_to = value
    case.updated_at = utc_now()
    add_case_event(session, case, "CASE_ASSIGNED", actor_reference, {"assigned_to": value})
    session.commit(); session.refresh(case); return case


def add_note(session, case, note: str, author_reference: str | None = None):
    if not note or not note.strip(): raise CaseBusinessError("note must not be empty")
    item = CaseNote(id=uuid4().hex, case_id=case.id, author_reference=author_reference, note=note.strip(), created_at=utc_now())
    session.add(item); add_case_event(session, case, "CASE_NOTE_ADDED", author_reference, {"note_id": item.id})
    case.updated_at = utc_now(); session.commit(); session.refresh(item); return item


def attach_exception(session, case, exception_id: str, actor_reference=None):
    exception = session.get(ReconciliationException, exception_id)
    if not exception: raise CaseBusinessError("Exception not found")
    if session.scalar(select(CaseExceptionLink).where(CaseExceptionLink.case_id == case.id, CaseExceptionLink.exception_id == exception.id)):
        raise CaseBusinessError("Exception is already attached to this case")
    # An exception has one primary reconciliation case for backward compatibility,
    # but the explicit link table allows intentional operational grouping into another case.
    session.add(CaseExceptionLink(case_id=case.id, exception_id=exception.id))
    if not exception.reconciliation_case_id:
        exception.reconciliation_case_id = case.id
    add_case_event(session, case, "EXCEPTION_ATTACHED", actor_reference, {"exception_id": exception.id})
    case.updated_at = utc_now(); session.commit(); session.refresh(case); return case
