
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Configure the application before importing modules that construct the DB engine.
DB_PATH = Path(__file__).with_name("e2e_test.db")
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{DB_PATH}",
        "AUTH_SECRET": "E" * 64,
        "AUTH_BOOTSTRAP_TOKEN": "E2E-BOOTSTRAP",
        "APP_ENV": "development",
        "CORS_ORIGINS": "http://localhost:3000",
        "AI_PROVIDER": "mock",
    }
)

from alembic.config import Config
from alembic import command
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models import Merchant


@pytest.fixture(scope="module", autouse=True)
def migrated_db():
    if DB_PATH.exists():
        DB_PATH.unlink()
    command.upgrade(Config("alembic.ini"), "head")
    session = SessionLocal()
    session.add(
        Merchant(
            id="e2e-merchant",
            name="E2E Merchant",
            email="e2e-merchant@example.com",
        )
    )
    session.commit()
    session.close()
    yield
    if DB_PATH.exists():
        DB_PATH.unlink()


@pytest.fixture()
def client():
    return TestClient(app)


def register_and_login(client):
    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPassword123!"},
    )
    if logged_in.status_code != 200:
        registered = client.post(
            "/api/v1/auth/register",
            headers={"X-Bootstrap-Token": "E2E-BOOTSTRAP"},
            json={
                "email": "admin@example.com",
                "password": "StrongPassword123!",
                "merchant_id": "e2e-merchant",
                "role": "ADMIN",
            },
        )
        assert registered.status_code == 201
        logged_in = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "StrongPassword123!"},
        )

    assert logged_in.status_code == 200
    token = logged_in.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_registration_requires_controlled_bootstrap(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "blocked@example.com",
            "password": "StrongPassword123!",
            "merchant_id": "e2e-merchant",
            "role": "ADMIN",
        },
    )
    assert response.status_code == 403


def test_registration_login_me_and_dashboard(client):
    headers = register_and_login(client)

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "admin@example.com"
    assert me.json()["merchant_id"] == "e2e-merchant"

    dashboard = client.get("/api/v1/dashboard/summary", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["total_payments"] == 0


def test_bad_credentials_and_invalid_token_are_rejected(client):
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401

    invalid_token = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert invalid_token.status_code == 401


def test_financial_reconciliation_case_and_rca_flow(client):
    headers = register_and_login(client)

    payment = client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "provider": "demo",
            "provider_payment_id": "pay_e2e_001",
            "provider_order_id": "ord_e2e_001",
            "amount": "1000.00",
            "currency": "INR",
            "status": "captured",
            "method": "card",
            "captured": True,
            "raw_data": {"source": "e2e"},
        },
    )
    assert payment.status_code == 201

    settlement = client.post(
        "/api/v1/settlements",
        headers=headers,
        json={
            "provider": "demo",
            "provider_settlement_id": "set_e2e_001",
            "provider_payment_id": "pay_e2e_001",
            "gross_amount": "1000.00",
            "fee": "25.00",
            "tax": "5.00",
            "net_amount": "960.00",
            "status": "processed",
            "settled_at": datetime.now(timezone.utc).isoformat(),
            "utr": "utr_e2e_001",
            "raw_data": {"source": "e2e"},
        },
    )
    assert settlement.status_code == 201

    reconciliation = client.post(
        "/api/v1/reconciliation/run", headers=headers
    )
    assert reconciliation.status_code == 200
    assert reconciliation.json()["created_cases"] == 1
    assert reconciliation.json()["mismatch"] == 1

    cases = client.get("/api/v1/reconciliation/cases", headers=headers)
    assert cases.status_code == 200
    assert len(cases.json()["items"]) == 1

    case_id = cases.json()["items"][0]["id"]
    case = client.get(f"/api/v1/reconciliation/cases/{case_id}", headers=headers)
    assert case.status_code == 200

    rca = client.get(f"/api/v1/rca/{case_id}", headers=headers)
    assert rca.status_code == 200
    assert rca.json()["root_cause_code"] == "SETTLEMENT_AMOUNT_MISMATCH"
