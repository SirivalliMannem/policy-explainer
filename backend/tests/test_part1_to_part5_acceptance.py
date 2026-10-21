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
from app.services.customer_verification import verify_customer
from app.services.policy_resolver import resolve_policy_from_question
from app.services.portfolio import answer_portfolio_question, portfolio_suggestions

client = TestClient(app)


def test_unknown_customer_verification_fails_and_does_not_leak_other_customers():
    """Asking about a nonexistent customer must return customer-not-found and 0 policies."""
    db = SessionLocal()
    try:
        # 1. Verification service directly
        res = resolve_policy_from_question("What are the policies of Sirivalli?", db)
        v = verify_customer(res, "What are the policies of Sirivalli?", None, None, db)
        assert v.status == "not_found"
        assert "Sirivalli" in v.message
        assert "I couldn't find a matching customer for 'Sirivalli'" in v.message

        # 2. Portfolio service directly
        p_ans = answer_portfolio_question("What are the policies of Sirivalli?", db)
        assert p_ans.scope == "not_found"
        assert len(p_ans.policies) == 0
        assert "Sirivalli" in p_ans.answer
        assert portfolio_suggestions(p_ans) == []

        # 3. Policy resolution endpoint from question
        resp = client.post("/api/policy-resolution/from-question", json={"question": "What are the policies of Sirivalli?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["customer_verification"]["status"] == "not_found"
        assert data.get("suggested_policies") == []

        # 4. Conversation question submission
        conv_resp = client.post("/api/conversations", json={})
        assert conv_resp.status_code in (200, 201)
        conv_id = conv_resp.json()["conversation_id"]

        ask_resp = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What are the policies of Sirivalli?"})
        assert ask_resp.status_code in (200, 201)
        ask_data = ask_resp.json()
        assert ask_data["status"] == "insufficient_evidence"
        assert len(ask_data.get("evidence", [])) == 0
        assert len(ask_data.get("citations", [])) == 0
        assert "Sirivalli" in ask_data["answer"]
        if ask_data.get("portfolio"):
            assert ask_data["portfolio"]["scope"] == "not_found"
            assert len(ask_data["portfolio"]["policies"]) == 0

        # Policy-specific question for unknown customer
        ask_resp2 = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What are the exclusions of Sirivalli?"})
        assert ask_resp2.status_code in (200, 201)
        ask_data2 = ask_resp2.json()
        assert ask_data2["status"] == "insufficient_evidence"
        assert len(ask_data2.get("evidence", [])) == 0
        assert len(ask_data2.get("citations", [])) == 0
        assert "Sirivalli" in ask_data2["answer"]
    finally:
        db.close()


def test_follow_up_questions_in_existing_conversation_use_context():
    """In an existing conversation, generic follow-up questions must use the verified policy without repeating the name."""
    db = SessionLocal()
    try:
        margaret = db.query(CoreAccount).filter(CoreAccount.name.ilike("%Margaret Chen%")).first()
        assert margaret is not None
        ho_policy = db.query(CorePolicy).filter(CorePolicy.account_id == margaret.id, CorePolicy.policy_number.startswith("HO")).first()
        assert ho_policy is not None

        # Create conversation bound to Margaret Chen's Homeowners policy
        conv_resp = client.post("/api/conversations", json={"policy_id": ho_policy.id})
        assert conv_resp.status_code in (200, 201)
        conv_id = conv_resp.json()["conversation_id"]

        # 1. Follow-up: "What is the deductible?"
        q1_resp = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What is the deductible?"})
        assert q1_resp.status_code in (200, 201)
        q1_data = q1_resp.json()
        assert q1_data["policy_context"]["policy_number"] == ho_policy.policy_number
        assert q1_data["policy_context"]["customer_name"] == margaret.name
        assert q1_data["status"] in ("answered", "insufficient_evidence")

        # 2. Follow-up: "What are the exclusions?"
        q2_resp = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What are the exclusions?"})
        assert q2_resp.status_code in (200, 201)
        q2_data = q2_resp.json()
        assert q2_data["policy_context"]["policy_number"] == ho_policy.policy_number
        assert q2_data["policy_context"]["customer_name"] == margaret.name

        # 3. Explicit reference matching current context: "What are the exclusions of Margaret Chen's policy?"
        q3_resp = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What are the exclusions of Margaret Chen's policy?"})
        assert q3_resp.status_code in (200, 201)
        q3_data = q3_resp.json()
        assert q3_data["policy_context"]["policy_number"] == ho_policy.policy_number

        # 4. Explicit policy number matching current context: "What are the exclusions of policy HO-2847-1193?"
        q4_resp = client.post(f"/api/conversations/{conv_id}/questions", json={"question": f"What are the exclusions of policy {ho_policy.policy_number}?"})
        assert q4_resp.status_code in (200, 201)
        q4_data = q4_resp.json()
        assert q4_data["policy_context"]["policy_number"] == ho_policy.policy_number

        # 5. Explicit reference to a different customer in the existing thread requires confirmation (409 Conflict)
        q5_resp = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What are the exclusions of Daniel Ortiz's policy?"})
        assert q5_resp.status_code == 409
    finally:
        db.close()


def test_context_restoration_and_switching():
    """Reopening a conversation or switching context must persist and restore policy context properly."""
    db = SessionLocal()
    try:
        policies = db.query(CorePolicy).all()
        p1 = policies[0]
        p2 = policies[1]

        # Create conversation with p1
        conv_resp = client.post("/api/conversations", json={"policy_id": p1.id})
        assert conv_resp.status_code in (200, 201)
        conv_id = conv_resp.json()["conversation_id"]

        # Reopen conversation
        get_conv = client.get(f"/api/conversations/{conv_id}")
        assert get_conv.status_code == 200
        assert get_conv.json()["policy_context"]["policy_id"] == p1.id

        # Switch context to p2
        switch_resp = client.post(f"/api/conversations/{conv_id}/context", json={"policy_id": p2.id, "confirm_different_customer": True})
        assert switch_resp.status_code == 200
        assert switch_resp.json()["policy_context"]["policy_id"] == p2.id

        # Verify restored context is now p2
        get_conv2 = client.get(f"/api/conversations/{conv_id}")
        assert get_conv2.status_code == 200
        assert get_conv2.json()["policy_context"]["policy_id"] == p2.id
    finally:
        db.close()
