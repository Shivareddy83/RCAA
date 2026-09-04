import hashlib
import json
from app.core.config import settings
from app.core.time import utc_now
from app.models import WebhookEvent
from app.providers.razorpay import RazorpayProvider
from app.repositories.webhooks import get_event
from app.ingestion import ingest_provider_payload, IngestionValidationError


def process_razorpay_webhook(session, raw: bytes, signature: str | None, event_id: str | None):
    if not signature or not settings.razorpay_webhook_secret:
        return None, False

    provider = RazorpayProvider(
        settings.razorpay_key_id,
        settings.razorpay_key_secret,
        settings.razorpay_webhook_secret,
    )
    if not provider.verify_webhook(raw, signature):
        return None, False

    payload = json.loads(raw)
    resolved_event_id = event_id or payload.get("event_id") or hashlib.sha256(raw).hexdigest()
    if get_event(session, "razorpay", resolved_event_id):
        return {"status": "duplicate"}, True

    event_type = payload.get("event", "unknown")
    entity = ((payload.get("payload") or {}).get("payment") or (payload.get("payload") or {}).get("refund") or (payload.get("payload") or {}).get("settlement") or {}).get("entity")
    try:
        if entity and event_type.startswith("payment."):
            ingest_provider_payload(session, provider, [entity], record_type="payment", source="razorpay_webhook")
        elif entity and event_type.startswith("refund."):
            ingest_provider_payload(session, provider, [entity], record_type="refund", source="razorpay_webhook")
        elif entity and event_type.startswith("settlement."):
            ingest_provider_payload(session, provider, [entity], record_type="settlement", source="razorpay_webhook")
    except (IngestionValidationError, KeyError) as exc:
        session.rollback()
        return {"status": "rejected", "error": str(exc)}, True

    session.add(WebhookEvent(provider="razorpay", event_id=resolved_event_id, event_type=event_type, signature_valid=True, processed=True, processed_at=utc_now(), payload={"event": event_type, "event_id": resolved_event_id}))
    session.commit()
    return {"status": "processed"}, True
