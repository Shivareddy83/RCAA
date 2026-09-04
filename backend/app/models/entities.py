from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint, Index, event, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.time import utc_now
from app.db.base import Base

class Merchant(Base):
    __tablename__='merchants'; id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid4())); name:Mapped[str]=mapped_column(String); email:Mapped[str]=mapped_column(String,unique=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    role: Mapped[str] = mapped_column(String, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

class Payment(Base):
    __tablename__='payments'; __table_args__=(UniqueConstraint('provider','provider_payment_id',name='uq_payment_provider_id'), Index('ix_payment_source_external','source','external_id'))
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid4())); provider:Mapped[str]=mapped_column(String,index=True); provider_payment_id:Mapped[str]=mapped_column(String,index=True); provider_order_id:Mapped[Optional[str]]=mapped_column(String,index=True); merchant_id:Mapped[Optional[str]]=mapped_column(ForeignKey('merchants.id')); amount:Mapped[Decimal]=mapped_column(Numeric(14,2)); currency:Mapped[str]=mapped_column(String,default='INR'); status:Mapped[str]=mapped_column(String); method:Mapped[Optional[str]]=mapped_column(String); captured:Mapped[bool]=mapped_column(Boolean,default=False); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now); captured_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True)); raw_data:Mapped[dict]=mapped_column(JSON,default=dict); source:Mapped[str]=mapped_column(String,default='manual_demo',index=True); external_id:Mapped[Optional[str]]=mapped_column(String,index=True); ingestion_batch_id:Mapped[Optional[str]]=mapped_column(String,index=True); received_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now); raw_reference:Mapped[Optional[str]]=mapped_column(String); updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now,onupdate=utc_now)
    refunds:Mapped[list['Refund']]=relationship(back_populates='payment'); settlements:Mapped[list['Settlement']]=relationship(back_populates='payment')
class Refund(Base):
    __tablename__='refunds'; __table_args__=(UniqueConstraint('provider','provider_refund_id',name='uq_refund_provider_id'), Index('ix_refund_source_external','source','external_id'))
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid4())); provider:Mapped[str]=mapped_column(String); merchant_id:Mapped[Optional[str]]=mapped_column(ForeignKey('merchants.id'),index=True); provider_refund_id:Mapped[str]=mapped_column(String,index=True); provider_payment_id:Mapped[str]=mapped_column(String,index=True); payment_id:Mapped[Optional[str]]=mapped_column(ForeignKey('payments.id')); amount:Mapped[Decimal]=mapped_column(Numeric(14,2)); status:Mapped[str]=mapped_column(String); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now); processed_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True)); raw_data:Mapped[dict]=mapped_column(JSON,default=dict); source:Mapped[str]=mapped_column(String,default='manual_demo',index=True); external_id:Mapped[Optional[str]]=mapped_column(String,index=True); ingestion_batch_id:Mapped[Optional[str]]=mapped_column(String,index=True); received_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now); raw_reference:Mapped[Optional[str]]=mapped_column(String); payment:Mapped[Optional[Payment]]=relationship(back_populates='refunds')
class Settlement(Base):
    __tablename__='settlements'; __table_args__=(UniqueConstraint('provider','provider_settlement_id',name='uq_settlement_provider_id'), Index('ix_settlement_source_external','source','external_id'))
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid4())); provider:Mapped[str]=mapped_column(String); merchant_id:Mapped[Optional[str]]=mapped_column(ForeignKey('merchants.id'),index=True); provider_settlement_id:Mapped[str]=mapped_column(String,index=True); provider_payment_id:Mapped[str]=mapped_column(String,index=True); payment_id:Mapped[Optional[str]]=mapped_column(ForeignKey('payments.id')); gross_amount:Mapped[Decimal]=mapped_column(Numeric(14,2)); fee:Mapped[Decimal]=mapped_column(Numeric(14,2),default=0); tax:Mapped[Decimal]=mapped_column(Numeric(14,2),default=0); net_amount:Mapped[Decimal]=mapped_column(Numeric(14,2)); status:Mapped[str]=mapped_column(String); settled_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); utr:Mapped[Optional[str]]=mapped_column(String); raw_data:Mapped[dict]=mapped_column(JSON,default=dict); source:Mapped[str]=mapped_column(String,default='manual_demo',index=True); external_id:Mapped[Optional[str]]=mapped_column(String,index=True); ingestion_batch_id:Mapped[Optional[str]]=mapped_column(String,index=True); received_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now); raw_reference:Mapped[Optional[str]]=mapped_column(String); payment:Mapped[Optional[Payment]]=relationship(back_populates='settlements')
class WebhookEvent(Base):
    __tablename__='webhook_events'; __table_args__=(UniqueConstraint('provider','event_id',name='uq_webhook_provider_event'),)
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid4())); provider:Mapped[str]=mapped_column(String); event_id:Mapped[str]=mapped_column(String); event_type:Mapped[str]=mapped_column(String); signature_valid:Mapped[bool]=mapped_column(Boolean); processed:Mapped[bool]=mapped_column(Boolean,default=False); payload:Mapped[dict]=mapped_column(JSON); received_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now); processed_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True))
class Case(Base):
    __tablename__='reconciliation_cases'
    __table_args__=(Index('ix_case_record_type_record_id','record_type','record_id'), Index('ix_case_reason_code','reason_code'))
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid4()))
    payment_id:Mapped[Optional[str]]=mapped_column(ForeignKey('payments.id'),index=True)
    record_id:Mapped[Optional[str]]=mapped_column(String,index=True)
    record_type:Mapped[str]=mapped_column(String,default='payment')
    case_type:Mapped[str]=mapped_column(String,index=True)
    severity:Mapped[str]=mapped_column(String)
    status:Mapped[str]=mapped_column(String,default='OPEN')
    case_number:Mapped[str]=mapped_column(String,unique=True,index=True)
    merchant_id:Mapped[Optional[str]]=mapped_column(String,index=True)
    title:Mapped[str]=mapped_column(String,default='RCAA operational case')
    description:Mapped[str]=mapped_column(Text,default='')
    priority:Mapped[str]=mapped_column(String,default='MEDIUM',index=True)
    assigned_to:Mapped[Optional[str]]=mapped_column(String,index=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now,onupdate=utc_now)
    resolution_code:Mapped[Optional[str]]=mapped_column(String)
    resolution_note:Mapped[Optional[str]]=mapped_column(Text)
    expected_amount:Mapped[Decimal]=mapped_column(Numeric(14,2))
    actual_amount:Mapped[Decimal]=mapped_column(Numeric(14,2))
    difference:Mapped[Decimal]=mapped_column(Numeric(14,2))
    confidence:Mapped[Decimal]=mapped_column(Numeric(4,2))
    match_method:Mapped[str]=mapped_column(String,default='NONE')
    match_confidence:Mapped[str]=mapped_column(String,default='NONE')
    matched_record_id:Mapped[Optional[str]]=mapped_column(String,index=True)
    reason_code:Mapped[str]=mapped_column(String,index=True,default='UNKNOWN')
    summary:Mapped[str]=mapped_column(Text)
    metadata_json:Mapped[dict]=mapped_column(JSON,default=dict)
    fingerprint:Mapped[str]=mapped_column(String,unique=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)
    resolved_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True))
    evidence:Mapped[list['Evidence']]=relationship(back_populates='case',cascade='all,delete-orphan')
    rca:Mapped[Optional['RCA']]=relationship(back_populates='case',cascade='all,delete-orphan',uselist=False)
    exceptions:Mapped[list['ReconciliationException']]=relationship(secondary='case_exception_links', back_populates='cases')
    notes:Mapped[list['CaseNote']]=relationship(back_populates='case',cascade='all,delete-orphan',order_by='CaseNote.created_at')
    events:Mapped[list['CaseEvent']]=relationship(back_populates='case',cascade='all,delete-orphan',order_by='CaseEvent.created_at')
class CaseExceptionLink(Base):
    __tablename__='case_exception_links'
    __table_args__=(UniqueConstraint('case_id','exception_id',name='uq_case_exception'),)
    case_id:Mapped[str]=mapped_column(ForeignKey('reconciliation_cases.id'),primary_key=True)
    exception_id:Mapped[str]=mapped_column(ForeignKey('reconciliation_exceptions.id'),primary_key=True)

class CaseNote(Base):
    __tablename__='case_notes'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid4()))
    case_id:Mapped[str]=mapped_column(ForeignKey('reconciliation_cases.id'),index=True)
    author_reference:Mapped[Optional[str]]=mapped_column(String)
    note:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now,index=True)
    case:Mapped[Case]=relationship(back_populates='notes')

class CaseEvent(Base):
    __tablename__='case_events'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid4()))
    case_id:Mapped[str]=mapped_column(ForeignKey('reconciliation_cases.id'),index=True)
    event_type:Mapped[str]=mapped_column(String,index=True)
    actor_reference:Mapped[Optional[str]]=mapped_column(String)
    metadata_json:Mapped[dict]=mapped_column(JSON,default=dict)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now,index=True)
    case:Mapped[Case]=relationship(back_populates='events')

class Evidence(Base):
    __tablename__='rca_evidence'
    __table_args__=(UniqueConstraint('fingerprint',name='uq_evidence_fingerprint'), Index('ix_evidence_case_type','reconciliation_case_id','evidence_type'))
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid4()))
    reconciliation_case_id:Mapped[str]=mapped_column(ForeignKey('reconciliation_cases.id'),index=True)
    evidence_type:Mapped[str]=mapped_column(String,index=True)
    source_entity_type:Mapped[Optional[str]]=mapped_column(String,index=True)
    source_record_id:Mapped[Optional[str]]=mapped_column(String,index=True)
    captured_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now,index=True)
    relevance:Mapped[str]=mapped_column(Text,default='')
    snapshot_json:Mapped[dict]=mapped_column(JSON,default=dict)
    description:Mapped[str]=mapped_column(Text,default='')
    metadata_json:Mapped[dict]=mapped_column(JSON,default=dict)
    fingerprint:Mapped[str]=mapped_column(String,index=True)
    case:Mapped[Case]=relationship(back_populates='evidence')

class RCA(Base):
    __tablename__='rca_results'
    __table_args__=(Index('ix_rca_root_cause','root_cause'), Index('ix_rca_engine_version','engine_version'), Index('ix_rca_case_fingerprint','reconciliation_case_id','fingerprint', unique=True))
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid4()))
    reconciliation_case_id:Mapped[str]=mapped_column(ForeignKey('reconciliation_cases.id'),unique=True)
    exception_id:Mapped[Optional[str]]=mapped_column(ForeignKey('reconciliation_exceptions.id'),index=True)
    root_cause:Mapped[str]=mapped_column(String)
    root_cause_category:Mapped[str]=mapped_column(String,default='UNKNOWN')
    explanation:Mapped[str]=mapped_column(Text)
    confidence:Mapped[Decimal]=mapped_column(Numeric(4,2))
    confidence_label:Mapped[str]=mapped_column(String,default='UNKNOWN')
    recommended_action:Mapped[str]=mapped_column(Text)
    evidence_ids_json:Mapped[list]=mapped_column(JSON,default=list)
    engine_version:Mapped[str]=mapped_column(String,default='rca-v1',index=True)
    fingerprint:Mapped[str]=mapped_column(String,index=True)
    generated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)
    case:Mapped[Case]=relationship(back_populates='rca')



class RCAHistory(Base):
    __tablename__='rca_result_history'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid4()))
    reconciliation_case_id:Mapped[str]=mapped_column(ForeignKey('reconciliation_cases.id'),index=True)
    exception_id:Mapped[Optional[str]]=mapped_column(String,index=True)
    root_cause:Mapped[str]=mapped_column(String)
    root_cause_category:Mapped[str]=mapped_column(String)
    confidence_label:Mapped[str]=mapped_column(String)
    explanation:Mapped[str]=mapped_column(Text)
    recommended_action:Mapped[str]=mapped_column(Text)
    evidence_ids_json:Mapped[list]=mapped_column(JSON,default=list)
    engine_version:Mapped[str]=mapped_column(String)
    fingerprint:Mapped[str]=mapped_column(String,index=True)
    generated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)
    archived_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)


class AIInvestigationAudit(Base):
    __tablename__ = 'ai_investigation_audits'
    __table_args__ = (UniqueConstraint('request_fingerprint', name='uq_ai_request_fingerprint'), Index('ix_ai_audit_case_created','case_id','created_at'))
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    case_id: Mapped[str] = mapped_column(ForeignKey('reconciliation_cases.id'), index=True)
    request_fingerprint: Mapped[str] = mapped_column(String, unique=True, index=True)
    evidence_fingerprint: Mapped[str] = mapped_column(String, index=True)
    prompt_version: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String, default='')
    result_fingerprint: Mapped[Optional[str]] = mapped_column(String)
    result_json: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, index=True)
    latency_ms: Mapped[Optional[int]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_event_merchant_timestamp", "merchant_id", "timestamp"),
        Index("ix_audit_event_action", "action"),
        Index("ix_audit_event_actor", "actor_user_id"),
        Index("ix_audit_event_resource", "resource_type", "resource_id"),
        Index("ix_audit_event_request", "request_id"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    merchant_id: Mapped[Optional[str]] = mapped_column(ForeignKey("merchants.id"), nullable=True, index=True)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String)
    actor_type: Mapped[str] = mapped_column(String, default="USER")
    action: Mapped[str] = mapped_column(String, index=True)
    resource_type: Mapped[str] = mapped_column(String)
    resource_id: Mapped[Optional[str]] = mapped_column(String)
    request_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    outcome: Mapped[str] = mapped_column(String, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    before_snapshot: Mapped[Optional[dict]] = mapped_column(JSON)
    after_snapshot: Mapped[Optional[dict]] = mapped_column(JSON)
    previous_event_hash: Mapped[Optional[str]] = mapped_column(String)
    event_hash: Mapped[str] = mapped_column(String, unique=True, index=True)


class IngestionBatch(Base):
    __tablename__ = 'ingestion_batches'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    source: Mapped[str] = mapped_column(String, index=True)
    provider: Mapped[Optional[str]] = mapped_column(String, index=True)
    merchant_id: Mapped[Optional[str]] = mapped_column(ForeignKey("merchants.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, default='STARTED', index=True)
    received_count: Mapped[int] = mapped_column(default=0)
    created_count: Mapped[int] = mapped_column(default=0)
    updated_count: Mapped[int] = mapped_column(default=0)
    duplicate_count: Mapped[int] = mapped_column(default=0)
    rejected_count: Mapped[int] = mapped_column(default=0)
    error_summary: Mapped[Optional[str]] = mapped_column(Text)
    record_type: Mapped[Optional[str]] = mapped_column(String, index=True)
    duplicate_records_json: Mapped[list] = mapped_column(JSON, default=list)

class BankTransaction(Base):
    __tablename__ = 'bank_transactions'
    __table_args__ = (UniqueConstraint('source', 'external_id', name='uq_bank_source_external'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    source: Mapped[str] = mapped_column(String, default='bank_csv', index=True)
    provider: Mapped[Optional[str]] = mapped_column(String, index=True)
    external_id: Mapped[str] = mapped_column(String, index=True)
    merchant_id: Mapped[Optional[str]] = mapped_column(ForeignKey('merchants.id'))
    reference: Mapped[Optional[str]] = mapped_column(String, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14,2))
    currency: Mapped[str] = mapped_column(String, default='INR')
    status: Mapped[str] = mapped_column(String, default='posted')
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    ingestion_batch_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    raw_reference: Mapped[Optional[str]] = mapped_column(String)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

class ReconciliationException(Base):
    __tablename__ = 'reconciliation_exceptions'
    __table_args__ = (Index('ix_exception_code_status','exception_code','status'), Index('ix_exception_severity','severity'))
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    reconciliation_case_id: Mapped[Optional[str]] = mapped_column(ForeignKey('reconciliation_cases.id'), unique=True)
    exception_code: Mapped[str] = mapped_column(String, index=True)
    severity: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default='OPEN', index=True)
    source: Mapped[Optional[str]] = mapped_column(String, index=True)
    merchant_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    primary_record_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    related_record_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(14,2))
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(14,2))
    difference: Mapped[Decimal] = mapped_column(Numeric(14,2))
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    fingerprint: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cases: Mapped[list[Case]] = relationship(secondary='case_exception_links', back_populates='exceptions')


# Stage 11: financial source records are append-only after creation.
# Operational code must create corrective records rather than rewriting financial truth.
_FINANCIAL_IMMUTABLE_FIELDS = {
    Payment: {"provider", "provider_payment_id", "provider_order_id", "merchant_id", "amount", "currency", "status", "method", "captured", "created_at", "captured_at", "raw_data", "source", "external_id", "ingestion_batch_id", "received_at", "raw_reference"},
    Refund: {"provider", "provider_refund_id", "merchant_id", "provider_payment_id", "payment_id", "amount", "status", "created_at", "processed_at", "raw_data", "source", "external_id", "ingestion_batch_id", "received_at", "raw_reference"},
    Settlement: {"provider", "provider_settlement_id", "merchant_id", "provider_payment_id", "payment_id", "gross_amount", "fee", "tax", "net_amount", "status", "settled_at", "utr", "raw_data", "source", "external_id", "ingestion_batch_id", "received_at", "raw_reference"},
}

def _reject_financial_mutation(mapper, connection, target):
    state = inspect(target)
    changed = [name for name in _FINANCIAL_IMMUTABLE_FIELDS[type(target)] if state.attrs[name].history.has_changes()]
    if changed:
        raise ValueError("Financial records are immutable after creation")

for _financial_model in _FINANCIAL_IMMUTABLE_FIELDS:
    event.listen(_financial_model, "before_update", _reject_financial_mutation)
