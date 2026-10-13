"""Comprehensive regression and integration tests for safe customer and policy switching."""

import os
import sys
import pytest
from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.db.database import SessionLocal
from app.models.policy import CorePolicy, CoreAccount
from app.models.conversation import Conversation, ContextSwitchAudit
from app.models.ledger import EvidenceLedger

client = TestClient(app)


@pytest.fixture(scope="module")
def seeded_policies():
    """Retrieve Margaret Chen's policies and Elena Moreau's policy."""
    db = SessionLocal()
    margaret = db.query(CoreAccount).filter(CoreAccount.name == "Margaret Chen").first()
    elena = db.query(CoreAccount).filter(CoreAccount.name == "Elena Moreau").first()
    assert margaret is not None and elena is not None

    m_home = db.query(CorePolicy).filter(CorePolicy.account_id == margaret.id, CorePolicy.policy_number == "HO-2847-1193").first()
    m_auto = db.query(CorePolicy).filter(CorePolicy.account_id == margaret.id, CorePolicy.policy_number == "PA-6120-7742").first()
    e_home = db.query(CorePolicy).filter(CorePolicy.account_id == elena.id, CorePolicy.policy_number == "HO-9021-4477").first()

    db.close()
    assert m_home is not None and m_auto is not None and e_home is not None
    return {
        "margaret_id": margaret.id,
        "m_home_id": m_home.id,
        "m_auto_id": m_auto.id,
        "elena_id": elena.id,
        "e_home_id": e_home.id,
    }


def test_scenario_a_same_customer_same_policy(seeded_policies):
    """Scenario A: Continuing a conversation with the same customer and policy."""
    # 1. Create conversation with Margaret Chen's HO policy
    conv_resp = client.post("/api/conversations", json={"policy_id": seeded_policies["m_home_id"]})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    # 2. Check context transition with same policy
    check_resp = client.get(f"/api/conversations/{conv_id}/context-check", params={"target_policy_id": seeded_policies["m_home_id"]})
    assert check_resp.status_code == 200
    check_data = check_resp.json()
    assert check_data["switch_type"] == "same_customer_same_policy"
    assert check_data["requires_confirmation"] is False
    assert check_data["allowed"] is True

    # 3. Post context update with same policy
    update_resp = client.post(f"/api/conversations/{conv_id}/context", json={"policy_id": seeded_policies["m_home_id"]})
    assert update_resp.status_code == 200
    assert update_resp.json()["policy_context"]["policy_id"] == seeded_policies["m_home_id"]


def test_scenario_b_same_customer_different_policy(seeded_policies):
    """Scenario B: Switching to another policy belonging to the same customer."""
    # 1. Create conversation with Margaret Chen HO policy
    conv_resp = client.post("/api/conversations", json={"policy_id": seeded_policies["m_home_id"]})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    # Ask an initial question on Homeowners policy
    q1 = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What is the deductible?"})
    assert q1.status_code == 201
    assert q1.json()["status"] == "answered"

    # 2. Check context transition to Margaret Chen's Auto policy
    check_resp = client.get(f"/api/conversations/{conv_id}/context-check", params={"target_policy_id": seeded_policies["m_auto_id"]})
    assert check_resp.status_code == 200
    check_data = check_resp.json()
    assert check_data["switch_type"] == "same_customer_different_policy"
    assert check_data["requires_confirmation"] is False
    assert check_data["target_customer"]["id"] == seeded_policies["margaret_id"]
    assert check_data["target_policy"]["policy_number"] == "PA-6120-7742"

    # 3. Switch context to Auto policy
    switch_resp = client.post(f"/api/conversations/{conv_id}/context", json={"policy_id": seeded_policies["m_auto_id"]})
    assert switch_resp.status_code == 200
    assert switch_resp.json()["policy_context"]["policy_number"] == "PA-6120-7742"
    assert switch_resp.json()["policy_context"]["customer_id"] == seeded_policies["margaret_id"]

    # 4. Subsequent question retrieves evidence for Auto policy
    q2 = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What is the policy number?"})
    assert q2.status_code == 201
    data2 = q2.json()
    assert data2["status"] == "answered"
    assert data2["policy_context"]["policy_number"] == "PA-6120-7742"
    assert "PA-6120-7742" in data2["answer"]

    # 5. Verify audit ledger preserves both and records context switch
    audit_resp = client.get(f"/api/conversations/{conv_id}/context-audit")
    assert audit_resp.status_code == 200
    audits = audit_resp.json()
    assert len(audits) >= 2  # initial_selection + same_customer_different_policy
    switches = [a for a in audits if a["switch_type"] == "same_customer_different_policy"]
    assert len(switches) == 1
    assert switches[0]["previous_policy_number"] == "HO-2847-1193"
    assert switches[0]["new_policy_number"] == "PA-6120-7742"
    assert switches[0]["outcome"] == "success"


def test_scenario_c_different_customer_unconfirmed_rejected(seeded_policies):
    """Scenario C: Switching to a different customer without explicit confirmation is rejected with 409."""
    conv_resp = client.post("/api/conversations", json={"policy_id": seeded_policies["m_home_id"]})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    # Check context transition returns requires_confirmation=True
    check_resp = client.get(f"/api/conversations/{conv_id}/context-check", params={"target_policy_id": seeded_policies["e_home_id"]})
    assert check_resp.status_code == 200
    check_data = check_resp.json()
    assert check_data["switch_type"] == "different_customer"
    assert check_data["requires_confirmation"] is True
    assert check_data["current_customer"]["id"] == seeded_policies["margaret_id"]
    assert check_data["target_customer"]["id"] == seeded_policies["elena_id"]

    # Attempt to switch without confirmation flag -> 409 Conflict
    reject_resp = client.post(f"/api/conversations/{conv_id}/context", json={"policy_id": seeded_policies["e_home_id"]})
    assert reject_resp.status_code == 409
    assert "different customer" in reject_resp.json()["detail"].lower()

    # Original conversation context MUST remain unchanged
    get_resp = client.get(f"/api/conversations/{conv_id}")
    assert get_resp.json()["policy_context"]["policy_id"] == seeded_policies["m_home_id"]

    # Audit records the rejected attempt
    audits = client.get(f"/api/conversations/{conv_id}/context-audit").json()
    rejected = [a for a in audits if a["outcome"] == "rejected"]
    assert len(rejected) == 1
    assert rejected[0]["switch_type"] == "different_customer"


def test_scenario_c_different_customer_start_new_conversation(seeded_policies):
    """Scenario C: Choosing Start New Conversation creates a clean, independent conversation."""
    # Conversation 1: Margaret Chen
    conv1 = client.post("/api/conversations", json={"policy_id": seeded_policies["m_home_id"]}).json()["conversation_id"]
    q1 = client.post(f"/api/conversations/{conv1}/questions", json={"question": "What is the deductible?"})
    assert q1.status_code == 201

    # User chooses "Start New Conversation" for Elena Moreau
    conv2_resp = client.post("/api/conversations", json={"policy_id": seeded_policies["e_home_id"]})
    assert conv2_resp.status_code == 201
    conv2 = conv2_resp.json()["conversation_id"]
    assert conv2 != conv1
    assert conv2_resp.json()["policy_context"]["customer_name"] == "Elena Moreau"

    # Conversation 2 has clean history (0 questions)
    history2 = client.get(f"/api/conversations/{conv2}/messages").json()
    assert len(history2) == 0

    # Conversation 1 is completely preserved
    history1 = client.get(f"/api/conversations/{conv1}/messages").json()
    assert len(history1) == 1
    assert history1[0]["answer"]["policy_context"]["customer_name"] == "Margaret Chen"


def test_scenario_c_different_customer_confirmed_switch(seeded_policies):
    """Scenario C: Choosing Switch Existing Conversation with confirmation updates context and writes audit."""
    conv_resp = client.post("/api/conversations", json={"policy_id": seeded_policies["m_home_id"]})
    conv_id = conv_resp.json()["conversation_id"]

    # Switch with confirm_different_customer=True
    switch_resp = client.post(
        f"/api/conversations/{conv_id}/context",
        json={"policy_id": seeded_policies["e_home_id"], "confirm_different_customer": True},
    )
    assert switch_resp.status_code == 200
    assert switch_resp.json()["policy_context"]["customer_name"] == "Elena Moreau"
    assert switch_resp.json()["policy_context"]["policy_number"] == "HO-9021-4477"

    # Verify audit ledger
    audits = client.get(f"/api/conversations/{conv_id}/context-audit").json()
    diff_switches = [a for a in audits if a["switch_type"] == "different_customer" and a["outcome"] == "success"]
    assert len(diff_switches) == 1
    assert diff_switches[0]["previous_customer_name"] == "Margaret Chen"
    assert diff_switches[0]["new_customer_name"] == "Elena Moreau"


def test_authorization_enforcement(seeded_policies):
    """Unauthorized employee receives 403 Forbidden on resolve, context-check, context-update, and questions."""
    unauth_headers = {
        "X-Employee-Id": "EMP-BAD-01",
        "X-Employee-Name": "Suspended User",
        "X-Employee-Role": "unauthorized",
    }

    # 1. Resolve endpoint
    r_resolve = client.post(
        "/api/policy-resolution/resolve",
        json={"policy_id": seeded_policies["m_home_id"]},
        headers=unauth_headers,
    )
    assert r_resolve.status_code == 403

    # 2. Search endpoint
    r_search = client.get("/api/policy-resolution/search?q=Chen", headers=unauth_headers)
    assert r_search.status_code == 403

    # 3. Create conversation with valid user
    conv_id = client.post("/api/conversations", json={"policy_id": seeded_policies["m_home_id"]}).json()["conversation_id"]

    # 4. Unauthorized user cannot switch context or ask questions
    r_switch = client.post(
        f"/api/conversations/{conv_id}/context",
        json={"policy_id": seeded_policies["m_auto_id"]},
        headers=unauth_headers,
    )
    assert r_switch.status_code in (403, 404)  # 404 because conversation belongs to another employee

    # 5. Conversation owned by unauthorized employee cannot access policy context
    conv_unauth = client.post("/api/conversations", json={}, headers=unauth_headers).json()["conversation_id"]
    r_set = client.post(
        f"/api/conversations/{conv_unauth}/context",
        json={"policy_id": seeded_policies["m_home_id"]},
        headers=unauth_headers,
    )
    assert r_set.status_code == 403


def test_customer_policy_relationship_validation(seeded_policies):
    """Mismatched customer_id in context update is rejected with 400 Bad Request."""
    conv_id = client.post("/api/conversations").json()["conversation_id"]

    # Pass Margaret Chen's policy with Elena Moreau's customer_id
    r = client.post(
        f"/api/conversations/{conv_id}/context",
        json={
            "policy_id": seeded_policies["m_home_id"],
            "customer_id": seeded_policies["elena_id"],  # Mismatch!
        },
    )
    assert r.status_code == 400
    assert "does not belong" in r.json()["detail"].lower()
