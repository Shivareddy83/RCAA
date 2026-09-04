from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from app.models import Payment, Settlement
from app.reconciliation.models import Candidate, MatchConfidence, MatchDecision, MatchMethod
from app.reconciliation.rules import ReconciliationRules


def _normalize(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value.lower() if value else None


def _references(payment: Payment) -> set[str]:
    values = {
        payment.provider_order_id,
        payment.raw_data.get("order_id"),
        payment.raw_data.get("merchant_order_reference"),
        payment.raw_data.get("provider_reference"),
    }
    return {normalized for value in values if (normalized := _normalize(value))}


def _settlement_references(settlement: Settlement) -> set[str]:
    values = {
        settlement.raw_data.get("order_id"),
        settlement.raw_data.get("merchant_order_reference"),
        settlement.raw_data.get("provider_reference"),
        settlement.raw_data.get("settlement_reference"),
    }
    return {normalized for value in values if (normalized := _normalize(value))}


def _payment_bank_references(payment: Payment) -> set[str]:
    values = {
        payment.raw_data.get("utr"),
        payment.raw_data.get("bank_reference"),
        payment.raw_data.get("settlement_reference"),
    }
    return {normalized for value in values if (normalized := _normalize(value))}


def _settlement_bank_references(settlement: Settlement) -> set[str]:
    values = {
        settlement.utr,
        settlement.raw_data.get("utr"),
        settlement.raw_data.get("bank_reference"),
        settlement.raw_data.get("settlement_reference"),
    }
    return {normalized for value in values if (normalized := _normalize(value))}


def _compatible_time(left, right) -> bool:
    if left.tzinfo is not None:
        left = left.astimezone().replace(tzinfo=None)
    if right.tzinfo is not None:
        right = right.astimezone().replace(tzinfo=None)
    return True


def _time_difference(left, right):
    _compatible_time(left, right)
    if left.tzinfo is not None:
        left = left.replace(tzinfo=None)
    if right.tzinfo is not None:
        right = right.replace(tzinfo=None)
    return abs(left - right)


def _candidate(item: Settlement) -> Candidate:
    return Candidate(
        record_id=item.id,
        record_type="settlement",
        amount=Decimal(item.net_amount),
        currency=str(item.raw_data.get("currency", "INR")).upper(),
        timestamp=item.settled_at,
    )


def match_payment_to_settlement(
    payment: Payment,
    settlements: list[Settlement],
    rules: ReconciliationRules,
) -> MatchDecision:
    candidates = [item for item in settlements if item.provider == payment.provider]
    if not candidates:
        return MatchDecision(False, reason="No settlement candidates for the payment provider.")

    payment_id = _normalize(payment.provider_payment_id)
    exact = [item for item in candidates if _normalize(item.provider_payment_id) == payment_id and payment_id]
    if len(exact) == 1:
        return MatchDecision(True, MatchMethod.EXACT_PAYMENT_ID, MatchConfidence.HIGH,
                             "Payment and settlement share the same provider payment ID.", exact[0].id)
    if len(exact) > 1:
        return MatchDecision(False, MatchMethod.EXACT_PAYMENT_ID, MatchConfidence.NONE,
                             "Multiple settlements share the same provider payment ID.",
                             candidates=tuple(_candidate(item) for item in exact))

    order_refs = _references(payment)
    order_matches = [item for item in candidates if order_refs & _settlement_references(item)]
    if len(order_matches) == 1:
        return MatchDecision(True, MatchMethod.ORDER_REFERENCE, MatchConfidence.HIGH,
                             "A normalized order/provider reference uniquely identifies the settlement.", order_matches[0].id)
    if len(order_matches) > 1:
        return MatchDecision(False, MatchMethod.ORDER_REFERENCE, MatchConfidence.NONE,
                             "Multiple settlements match the payment order/reference.",
                             candidates=tuple(_candidate(item) for item in order_matches))

    bank_refs = _payment_bank_references(payment)
    bank_matches = [item for item in candidates if bank_refs & _settlement_bank_references(item)]
    if len(bank_matches) == 1:
        return MatchDecision(True, MatchMethod.UTR_REFERENCE, MatchConfidence.HIGH,
                             "A normalized UTR/bank/settlement reference uniquely identifies the settlement.", bank_matches[0].id)
    if len(bank_matches) > 1:
        return MatchDecision(False, MatchMethod.UTR_REFERENCE, MatchConfidence.NONE,
                             "Multiple settlements match the payment bank reference.",
                             candidates=tuple(_candidate(item) for item in bank_matches))

    window = timedelta(minutes=rules.timestamp_tolerance_minutes)
    amount_matches = []
    for item in candidates:
        currency = str(item.raw_data.get("currency", payment.currency)).upper()
        if currency != str(payment.currency).upper():
            continue
        amount = Decimal(item.net_amount)
        if abs(amount - Decimal(payment.amount)) <= rules.amount_tolerance and _time_difference(item.settled_at, payment.created_at) <= window:
            amount_matches.append(item)
    if len(amount_matches) == 1:
        method = MatchMethod.TOLERANCE_MATCH if rules.amount_tolerance else MatchMethod.AMOUNT_CURRENCY_TIME
        reason = "Settlement matches currency, amount tolerance, and configured timestamp tolerance."
        return MatchDecision(True, method, MatchConfidence.MEDIUM, reason, amount_matches[0].id)
    if len(amount_matches) > 1:
        return MatchDecision(False, MatchMethod.AMOUNT_CURRENCY_TIME, MatchConfidence.NONE,
                             "Multiple settlements satisfy the amount, currency, and time-window rule.",
                             candidates=tuple(_candidate(item) for item in amount_matches))

    return MatchDecision(False, reason="No deterministic matching rule produced a unique settlement.")
