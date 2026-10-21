"""Customer verification: the first step, before any policy information is retrieved."""

import uuid
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

import app.api.routes.conversations as conversation_routes
from app.main import app
from app.services.ai_client import ai_client

client = TestClient(app)


def headers(emp: str = "EMP-VERIFY-01") -> dict:
    return {"X-Employee-Id": emp, "X-Employee-Name": quote("Verify Tester"), "X-Employee-Role": "csr"}


@pytest.fixture(autouse=True)
def rules_only(monkeypatch):
    # Verification must not depend on the language model.
    monkeypatch.setattr(ai_client, "interpret", lambda *a, **k: None)
    monkeypatch.setattr(conversation_routes, "interpret_question", lambda *a, **k: None)


def verify(question: str, conversation_id=None, emp: str = "EMP-VERIFY-01") -> dict:
    body = {"question": question}
    if conversation_id:
        body["conversation_id"] = conversation_id
    res = client.post("/api/policy-resolution/from-question", json=body, headers=headers(emp))
    assert res.status_code == 200, res.text
    return res.json()["customer_verification"]


@pytest.mark.parametrize(
    "question, matched_on, customer",
    [
        ("What is Margaret Chen's deductible?", "customer_name", "Margaret Chen"),
        ("What is the deductible on HO-2847-1193?", "policy_number", "Margaret Chen"),
        ("margaret.chen@example.com asked about her deductible", "email", "Margaret Chen"),
        ("Who is the adjuster on CLM-2026-00417?", "claim_number", "Daniel Ortiz"),
        ("Is Priya Raghavan's jewelry covered?", "customer_name", "Priya Raghavan"),
    ],
)
def test_a_customer_in_the_records_is_verified(question, matched_on, customer):
    v = verify(question)
    assert v["status"] == "verified" and v["matched_on"] == matched_on
    assert [c["name"] for c in v["customers"]] == [customer]
    assert v["customers"][0]["account_number"].startswith("ACCT-")


def test_a_name_shared_by_several_customers_is_ambiguous():
    v = verify("What is Chen's deductible?")
    assert v["status"] == "ambiguous"
    assert sorted(c["name"] for c in v["customers"]) == ["David Chen", "Margaret Chen"]
    assert v["message"] == "2 customers in the records match: David Chen and Margaret Chen."


@pytest.mark.parametrize(
    "question, reference",
    [
        ("What is John Smith's deductible?", "John Smith"),
        ("How many policies does John Smith have?", "John Smith"),
        ("Who is the adjuster on CLM-2026-99999?", "CLM-2026-99999"),
        ("Caller at (999) 555-0000 has a question", "(999) 555-0000"),
    ],
)
def test_a_customer_not_in_the_records_is_not_found(question, reference):
    v = verify(question)
    assert v["status"] == "not_found" and v["reference"] == reference
    assert v["customers"] == []


def test_no_customer_named_and_none_selected():
    assert verify("What is the deductible?")["status"] == "not_named"


def test_the_customer_selected_in_the_conversation_counts_as_verified():
    emp = f"EMP-VERIFY-{uuid.uuid4().hex[:6]}"
    policy_id = client.post("/api/policy-resolution/from-question", json={"question": "HO-2847-1193"},
                            headers=headers(emp)).json()["policy"]["policy_id"]
    conv = client.post("/api/conversations", json={"policy_id": policy_id}, headers=headers(emp)).json()["conversation_id"]
    v = verify("What is the deductible?", conv, emp)
    assert v["status"] == "verified" and v["matched_on"] == "conversation"
    assert v["customers"][0]["name"] == "Margaret Chen"
    client.post(f"/api/conversations/{conv}/archive", headers=headers(emp))


def test_the_answer_records_how_its_customer_was_verified():
    emp = f"EMP-VERIFY-{uuid.uuid4().hex[:6]}"
    conv = client.post("/api/conversations", json={}, headers=headers(emp)).json()["conversation_id"]
    question = "What is the premium on HO-2847-1193?"
    resolution = client.post("/api/policy-resolution/from-question", json={"question": question, "conversation_id": conv},
                             headers=headers(emp)).json()
    client.post(f"/api/conversations/{conv}/context", json={"policy_id": resolution["policy"]["policy_id"]}, headers=headers(emp))
    answer = client.post(f"/api/conversations/{conv}/questions", json={"question": question}, headers=headers(emp))
    assert answer.status_code == 201, answer.text
    recorded = answer.json()["retrieval"]["customer_verification"]
    assert recorded["status"] == "verified" and recorded["matched_on"] == "policy_number"
    # Reopening the conversation shows the same verification, read from the ledger.
    stored = client.get(f"/api/conversations/{conv}/messages", headers=headers(emp)).json()[-1]["answer"]
    assert stored["retrieval"]["customer_verification"] == recorded
    client.post(f"/api/conversations/{conv}/archive", headers=headers(emp))
