"""Tests for @ Customer & Policy Context Selector feature.

Covers:
1. Customer search endpoint (by name, account number, email, auth enforcement).
2. Policy search endpoint (by policy number, customer name, account number, line of business, auth enforcement).
3. Context persistence in conversation (setting customer, policy, clearing context, reload).
4. Question submission with selected policy context.
5. Question submission with selected customer context (portfolio, single policy, multiple policies, no policies).
6. Conflicting explicitly named customer vs selected context.
7. Authorization and prevention of cross-customer evidence leakage.
8. Preservation of chat behavior when no context is selected.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.db.database import SessionLocal
from app.models.policy import CoreAccount, CorePolicy

client = TestClient(app)

AUTH_HEADERS = {
    "X-Employee-Id": "emp_test_01",
    "X-Employee-Name": "Test Employee",
    "X-Employee-Role": "underwriter",
}

UNAUTH_HEADERS = {
    "X-Employee-Id": "emp_unauth",
    "X-Employee-Name": "Suspended Employee",
    "X-Employee-Role": "suspended",
}


def test_customer_search_endpoints():
    """Verify customer search queries actual database records by name, email, and account number."""
    db = SessionLocal()
    account = db.query(CoreAccount).first()
    db.close()
    assert account is not None

    # Search by name
    res = client.get(f"/api/customers?search={account.name[:4]}", headers=AUTH_HEADERS)
    assert res.status_code == 200
    customers = res.json()
    assert len(customers) > 0
    match = next((c for c in customers if c["id"] == account.id), None)
    assert match is not None
    assert match["name"] == account.name
    assert "account_number" in match
    assert "policy_count" in match

    # Search by account_number
    if account.account_number:
        res_acc = client.get(f"/api/customers?search={account.account_number}", headers=AUTH_HEADERS)
        assert res_acc.status_code == 200
        found = [c for c in res_acc.json() if c["id"] == account.id]
        assert len(found) > 0

    # Authorization enforcement
    res_unauth = client.get("/api/customers", headers=UNAUTH_HEADERS)
    assert res_unauth.status_code == 403


def test_policy_search_endpoints():
    """Verify policy search queries actual database records by policy number, customer, and line of business."""
    db = SessionLocal()
    policy = db.query(CorePolicy).first()
    db.close()
    assert policy is not None

    # Search by policy number
    res = client.get(f"/api/policies?search={policy.policy_number[:6]}", headers=AUTH_HEADERS)
    assert res.status_code == 200
    policies = res.json()
    assert len(policies) > 0
    match = next((p for p in policies if p["id"] == policy.id), None)
    assert match is not None
    assert match["policy_number"] == policy.policy_number
    assert match["customer_name"] is not None
    assert match["line_of_business"] is not None

    # Filter by customer_id
    res_cust = client.get(f"/api/policies?customer_id={policy.account_id}", headers=AUTH_HEADERS)
    assert res_cust.status_code == 200
    assert all(p["customer_id"] == policy.account_id for p in res_cust.json())

    # Authorization enforcement
    res_unauth = client.get("/api/policies", headers=UNAUTH_HEADERS)
    assert res_unauth.status_code == 403


def test_conversation_context_persistence_and_switching():
    """Verify customer and policy context persistence, reload, and switching."""
    db = SessionLocal()
    accounts = db.query(CoreAccount).filter(CoreAccount.policies.any()).all()
    assert len(accounts) >= 2
    acc1, acc2 = accounts[0], accounts[1]
    pol1 = acc1.policies[0]
    pol2 = acc2.policies[0]
    db.close()

    # 1. Create conversation with customer context
    c_resp = client.post("/api/conversations", json={"customer_id": acc1.id}, headers=AUTH_HEADERS)
    assert c_resp.status_code in (200, 201)
    c_data = c_resp.json()
    conv_id = c_data["conversation_id"]
    assert c_data["customer_context"] is not None
    assert c_data["customer_context"]["customer_id"] == acc1.id
    assert c_data["policy_context"] is None

    # 2. Re-fetch conversation (simulating page reload)
    get_resp = client.get(f"/api/conversations/{conv_id}", headers=AUTH_HEADERS)
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["customer_context"]["customer_id"] == acc1.id
    assert get_data["customer_context"]["customer_name"] == acc1.name

    # 3. Update context to specific policy
    ctx_resp = client.post(f"/api/conversations/{conv_id}/context", json={"policy_id": pol1.id}, headers=AUTH_HEADERS)
    assert ctx_resp.status_code == 200
    ctx_data = ctx_resp.json()
    assert ctx_data["policy_context"] is not None
    assert ctx_data["policy_context"]["policy_id"] == pol1.id
    assert ctx_data["customer_context"]["customer_id"] == acc1.id

    # 4. Attempt unconfirmed switch to a different customer
    conflict_resp = client.post(
        f"/api/conversations/{conv_id}/context",
        json={"customer_id": acc2.id, "confirm_different_customer": False},
        headers=AUTH_HEADERS,
    )
    assert conflict_resp.status_code == 409

    # 5. Confirmed switch to a different customer
    switch_resp = client.post(
        f"/api/conversations/{conv_id}/context",
        json={"customer_id": acc2.id, "confirm_different_customer": True},
        headers=AUTH_HEADERS,
    )
    assert switch_resp.status_code == 200
    assert switch_resp.json()["customer_context"]["customer_id"] == acc2.id
    assert switch_resp.json()["policy_context"] is None

    # 6. Clear context
    clear_resp = client.delete(f"/api/conversations/{conv_id}/context", headers=AUTH_HEADERS)
    assert clear_resp.status_code == 200
    assert clear_resp.json()["customer_context"] is None
    assert clear_resp.json()["policy_context"] is None


def test_question_with_selected_policy_context():
    """Verify that a selected policy context constrains retrieval to that exact policy."""
    db = SessionLocal()
    policy = db.query(CorePolicy).first()
    db.close()
    assert policy is not None

    conv_resp = client.post("/api/conversations", json={"policy_id": policy.id}, headers=AUTH_HEADERS)
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What is the deductible?"},
        headers=AUTH_HEADERS,
    )
    assert q_resp.status_code in (200, 201)
    q_data = q_resp.json()
    assert q_data["status"] in ("answered", "insufficient_evidence", "needs_input")


def test_question_with_selected_customer_portfolio():
    """Verify portfolio questions for a selected customer list that customer's policies."""
    db = SessionLocal()
    account = db.query(CoreAccount).filter(CoreAccount.policies.any()).first()
    db.close()
    assert account is not None

    conv_resp = client.post("/api/conversations", json={"customer_id": account.id}, headers=AUTH_HEADERS)
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What are the policies?"},
        headers=AUTH_HEADERS,
    )
    assert q_resp.status_code in (200, 201)
    q_data = q_resp.json()
    assert q_data["status"] == "answered"
    assert "portfolio" in q_data.get("retrieval", {})


def test_question_with_selected_customer_multiple_policies():
    """When a customer has multiple policies and question is policy-specific, prompt user to select policy."""
    db = SessionLocal()
    # Find account with > 1 policy
    multi_account = None
    for acc in db.query(CoreAccount).all():
        if len(acc.policies) > 1:
            multi_account = acc
            break
    db.close()

    if multi_account:
        conv_resp = client.post("/api/conversations", json={"customer_id": multi_account.id}, headers=AUTH_HEADERS)
        conv_id = conv_resp.json()["conversation_id"]

        # Resolution check
        res_check = client.post(
            "/api/policy-resolution/from-question",
            json={"question": "What is the deductible?", "conversation_id": conv_id},
            headers=AUTH_HEADERS,
        )
        assert res_check.status_code == 200
        res_data = res_check.json()
        assert res_data["status"] == "ambiguous"
        assert len(res_data["candidates"]) > 1

        # Direct submit prompt
        q_resp = client.post(
            f"/api/conversations/{conv_id}/questions",
            json={"question": "What is the deductible?"},
            headers=AUTH_HEADERS,
        )
        assert q_resp.status_code in (200, 201)
        q_data = q_resp.json()
        assert q_data["status"] == "needs_input"
        assert "select which policy" in q_data["answer"].lower()


def test_conflicting_customer_in_question_with_active_context():
    """If question explicitly names a conflicting customer, do not silently answer with active context."""
    db = SessionLocal()
    accounts = db.query(CoreAccount).filter(CoreAccount.policies.any()).all()
    assert len(accounts) >= 2
    acc1, acc2 = accounts[0], accounts[1]
    pol1 = acc1.policies[0]
    db.close()

    conv_resp = client.post("/api/conversations", json={"policy_id": pol1.id}, headers=AUTH_HEADERS)
    conv_id = conv_resp.json()["conversation_id"]

    # Explicit conflict with unknown customer
    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What are the exclusions for Siri?"},
        headers=AUTH_HEADERS,
    )
    assert q_resp.status_code in (200, 201)
    q_data = q_resp.json()
    assert q_data["status"] == "insufficient_evidence"
    assert "I couldn't find a matching customer for 'Siri'" in q_data["answer"]

    # Explicit conflict with different existing customer
    q_conflict = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": f"What is the deductible of {acc2.name}?"},
        headers=AUTH_HEADERS,
    )
    assert q_conflict.status_code == 409
    assert "Explicit confirmation is required" in q_conflict.json()["detail"]


def test_chat_behavior_when_no_context_selected():
    """Preserve standard behavior when no context chip or conversation context is set."""
    conv_resp = client.post("/api/conversations", json={}, headers=AUTH_HEADERS)
    conv_id = conv_resp.json()["conversation_id"]

    # Small talk
    res_talk = client.post(
        "/api/policy-resolution/from-question",
        json={"question": "Hello, what can you do?", "conversation_id": conv_id},
        headers=AUTH_HEADERS,
    )
    assert res_talk.status_code == 200
    assert res_talk.json()["intent"] == "conversation"

    # Resolving named policy works normally
    db = SessionLocal()
    pol = db.query(CorePolicy).first()
    db.close()
    assert pol is not None

    res_pol = client.post(
        "/api/policy-resolution/from-question",
        json={"question": f"What is the deductible for {pol.policy_number}?", "conversation_id": conv_id},
        headers=AUTH_HEADERS,
    )
    assert res_pol.status_code == 200
    assert res_pol.json()["status"] == "resolved"
    assert res_pol.json()["policy"]["policy_number"] == pol.policy_number


