"""Regression tests for: Customer Not Found — Stop All Suggestions and Policy Resolution.

Requirements:
1. Unknown customer in the first question:
   - Returns customer-not-found message:
     "I couldn't find a matching customer for '<name>'. Please verify the customer name or provide a valid policy number."
   - Does not display suggestions, recent policies, or policy selection cards.
2. The same unknown customer in a subsequent question:
   - Consistently returns customer-not-found message without leaking other customers' policies.
3. An unknown customer after a valid customer's policy was previously selected:
   - Does not inherit policy context from the previous question.
   - Fails customer verification immediately without resolving from the active policy.
4. A valid customer with no matching policy evidence:
   - Preserves existing evidence-based fallback behavior (insufficient_evidence).
5. A valid customer with matching policy evidence:
   - Normal retrieval and factual/grounded answering succeed.
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
from app.models.policy import CorePolicy, CoreAccount

client = TestClient(app)


def test_unknown_customer_first_question():
    """1. An unknown customer in the first question must fail customer verification and return 0 suggestions."""
    # Policy resolution endpoint
    res1 = client.post("/api/policy-resolution/from-question", json={"question": "What are the policies of Siri?"})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "not_found"
    assert data1["customer_verification"]["status"] == "not_found"
    assert "Siri" in data1["customer_verification"]["message"]
    assert "I couldn't find a matching customer for 'Siri'" in data1["message"]
    assert data1.get("suggested_policies") == []
    assert data1.get("suggestions") == []
    assert data1.get("candidates") == []
    assert data1.get("policy") is None

    # Conversation submission
    conv_resp = client.post("/api/conversations", json={})
    assert conv_resp.status_code in (200, 201)
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What are the policies of Siri?"})
    assert q_resp.status_code in (200, 201)
    q_data = q_resp.json()
    assert q_data["status"] == "insufficient_evidence"
    assert "I couldn't find a matching customer for 'Siri'" in q_data["answer"]
    assert q_data.get("suggested_questions") == []
    assert q_data.get("evidence") == []
    assert q_data.get("citations") == []
    assert q_data.get("policy_context") is None


def test_same_unknown_customer_subsequent_question():
    """2. The same unknown customer in subsequent questions consistently returns customer-not-found."""
    conv_resp = client.post("/api/conversations", json={})
    assert conv_resp.status_code in (200, 201)
    conv_id = conv_resp.json()["conversation_id"]

    # Question 1: "What are the policies of Siri?"
    res1 = client.post("/api/policy-resolution/from-question", json={"question": "What are the policies of Siri?", "conversation_id": conv_id})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "not_found"
    assert data1.get("suggested_policies") == []
    assert data1.get("suggestions") == []

    q1 = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What are the policies of Siri?"})
    assert q1.status_code in (200, 201)
    assert "I couldn't find a matching customer for 'Siri'" in q1.json()["answer"]
    assert q1.json().get("suggested_questions") == []
    assert q1.json().get("policy_context") is None

    # Question 2: "What are the exclusions of Siri?"
    res2 = client.post("/api/policy-resolution/from-question", json={"question": "What are the exclusions of Siri?", "conversation_id": conv_id})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "not_found"
    assert data2["customer_verification"]["status"] == "not_found"
    assert "I couldn't find a matching customer for 'Siri'" in data2["message"]
    assert data2.get("suggested_policies") == []
    assert data2.get("suggestions") == []
    assert data2.get("candidates") == []
    assert data2.get("policy") is None

    q2 = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What are the exclusions of Siri?"})
    assert q2.status_code in (200, 201)
    d2 = q2.json()
    assert d2["status"] == "insufficient_evidence"
    assert "I couldn't find a matching customer for 'Siri'" in d2["answer"]
    assert d2.get("suggested_questions") == []
    assert d2.get("evidence") == []
    assert d2.get("citations") == []
    assert d2.get("policy_context") is None

    # Question 3: "What is the deductible for Siri?"
    res3 = client.post("/api/policy-resolution/from-question", json={"question": "What is the deductible for Siri?", "conversation_id": conv_id})
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["status"] == "not_found"
    assert data3.get("suggested_policies") == []
    assert data3.get("suggestions") == []

    q3 = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What is the deductible for Siri?"})
    assert q3.status_code in (200, 201)
    assert "I couldn't find a matching customer for 'Siri'" in q3.json()["answer"]
    assert q3.json().get("suggested_questions") == []
    assert q3.json().get("policy_context") is None


def test_unknown_customer_after_valid_customer_policy_selected():
    """3. An unknown customer after a valid customer's policy was previously selected must not inherit context."""
    db = SessionLocal()
    try:
        margaret = db.query(CoreAccount).filter(CoreAccount.name.ilike("%Margaret Chen%")).first()
        assert margaret is not None
        ho_policy = db.query(CorePolicy).filter(CorePolicy.account_id == margaret.id, CorePolicy.policy_number.startswith("HO")).first()
        assert ho_policy is not None

        # Start conversation with Margaret Chen's policy
        conv_resp = client.post("/api/conversations", json={"policy_id": ho_policy.id})
        assert conv_resp.status_code in (200, 201)
        conv_id = conv_resp.json()["conversation_id"]

        # Valid question about the active policy
        q_valid = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What is the deductible?"})
        assert q_valid.status_code in (200, 201)
        valid_data = q_valid.json()
        assert valid_data["policy_context"]["customer_name"] == margaret.name
        assert valid_data["policy_context"]["policy_number"] == ho_policy.policy_number

        # Now ask about unknown customer "Siri" in the same conversation
        # Policy resolution must report not_found and not leak Margaret Chen's policies
        res_siri = client.post("/api/policy-resolution/from-question", json={"question": "What are the exclusions of Siri?", "conversation_id": conv_id})
        assert res_siri.status_code == 200
        data_siri = res_siri.json()
        assert data_siri["status"] == "not_found"
        assert data_siri["customer_verification"]["status"] == "not_found"
        assert "I couldn't find a matching customer for 'Siri'" in data_siri["message"]
        assert data_siri.get("suggested_policies") == []
        assert data_siri.get("suggestions") == []
        assert data_siri.get("policy") is None

        # Question submission must not answer from Margaret Chen's policy
        q_siri = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What are the exclusions of Siri?"})
        assert q_siri.status_code in (200, 201)
        siri_ans = q_siri.json()
        assert siri_ans["status"] == "insufficient_evidence"
        assert "I couldn't find a matching customer for 'Siri'" in siri_ans["answer"]
        assert siri_ans.get("suggested_questions") == []
        assert siri_ans.get("policy_context") is None
        assert siri_ans.get("evidence") == []

        # Portfolio question about unknown customer must also not leak Margaret Chen
        q_siri_port = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What are the policies of Siri?"})
        assert q_siri_port.status_code in (200, 201)
        port_ans = q_siri_port.json()
        assert "I couldn't find a matching customer for 'Siri'" in port_ans["answer"]
        assert port_ans.get("suggested_questions") == []
        assert port_ans.get("policy_context") is None

        # Next generic question without naming a customer still retains Margaret Chen context
        q_next = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What is the policy term?"})
        assert q_next.status_code in (200, 201)
        next_data = q_next.json()
        assert next_data["policy_context"]["customer_name"] == margaret.name
    finally:
        db.close()


def test_valid_customer_no_matching_policy_evidence():
    """4. A valid customer with no matching policy evidence retains evidence-based fallback."""
    db = SessionLocal()
    try:
        margaret = db.query(CoreAccount).filter(CoreAccount.name.ilike("%Margaret Chen%")).first()
        assert margaret is not None
        ho_policy = db.query(CorePolicy).filter(CorePolicy.account_id == margaret.id, CorePolicy.policy_number.startswith("HO")).first()
        assert ho_policy is not None

        conv_resp = client.post("/api/conversations", json={"policy_id": ho_policy.id})
        assert conv_resp.status_code in (200, 201)
        conv_id = conv_resp.json()["conversation_id"]

        # Question on something policy forms do not cover/address
        q_resp = client.post(
            f"/api/conversations/{conv_id}/questions",
            json={"question": "Does this policy cover damage from a nuclear war?"},
        )
        assert q_resp.status_code in (200, 201)
        data = q_resp.json()
        # Customer verification succeeded
        assert data.get("retrieval", {}).get("customer_verification", {}).get("status") == "verified"
        assert data["policy_context"]["customer_name"] == margaret.name
        # Evidence-based fallback behavior: insufficient evidence when forms do not address the query
        assert data["status"] == "insufficient_evidence"
        assert data.get("guardrail_status") == "no_evidence"
    finally:
        db.close()


def test_valid_customer_with_matching_policy_evidence():
    """5. A valid customer with matching policy evidence retrieves evidence and answers correctly."""
    db = SessionLocal()
    try:
        margaret = db.query(CoreAccount).filter(CoreAccount.name.ilike("%Margaret Chen%")).first()
        assert margaret is not None
        ho_policy = db.query(CorePolicy).filter(CorePolicy.account_id == margaret.id, CorePolicy.policy_number.startswith("HO")).first()
        assert ho_policy is not None

        # Policy resolution succeeds
        res = client.post("/api/policy-resolution/from-question", json={"question": "What is Margaret Chen's deductible?"})
        assert res.status_code == 200
        data = res.json()
        assert data["customer_verification"]["status"] == "verified"
        assert data["customer_verification"]["customers"][0]["name"] == margaret.name

        # Factual lookup question answering succeeds with evidence
        conv_resp = client.post("/api/conversations", json={"policy_id": ho_policy.id})
        assert conv_resp.status_code in (200, 201)
        conv_id = conv_resp.json()["conversation_id"]

        q_resp = client.post(f"/api/conversations/{conv_id}/questions", json={"question": "What is the deductible?"})
        assert q_resp.status_code in (200, 201)
        q_data = q_resp.json()
        assert q_data["status"] == "answered"
        assert len(q_data.get("evidence", [])) > 0
        assert q_data["policy_context"]["customer_name"] == margaret.name
        assert q_data["policy_context"]["policy_number"] == ho_policy.policy_number
    finally:
        db.close()
