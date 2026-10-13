"""Tests for policy metadata retrieval, portfolio routing, and authorization."""

import os
import sys
import pytest
from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.db.database import SessionLocal
from app.models.policy import CorePolicy
from app.models.ledger import EvidenceLedger

client = TestClient(app)


@pytest.fixture(scope="module")
def elena_policy_id():
    """Retrieve Elena Moreau's Homeowners policy ID."""
    db = SessionLocal()
    policy = db.query(CorePolicy).filter(CorePolicy.policy_number == "HO-9021-4477").first()
    db.close()
    assert policy is not None, "Elena Moreau's policy HO-9021-4477 must exist in database"
    return policy.id


def test_what_policy_do_we_have_with_selected_policy(elena_policy_id):
    """Test 'What policy do we have?' with a selected policy returns grounded policy metadata."""
    # 1. Create a conversation and set active policy context
    conv_resp = client.post("/api/conversations", json={"policy_id": elena_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    # 2. Submit question
    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What policy do we have?"},
    )
    assert q_resp.status_code == 201
    data = q_resp.json()

    assert data["status"] == "answered"
    assert data["confidence"] in ("high", "medium")
    assert data["guardrail_status"] == "passed"
    assert "HO-9021-4477" in data["answer"] or "Homeowners" in data["answer"]

    # Verify evidence contains policy_meta
    meta_evidence = [e for e in data["evidence"] if e["source_type"] == "policy_meta"]
    assert len(meta_evidence) >= 1
    assert meta_evidence[0]["source_id"] == elena_policy_id
    assert "HO-9021-4477" in meta_evidence[0]["content"]

    # Verify traceable citations
    assert len(data["citations"]) >= 1
    assert any("HO-9021-4477" in (c.get("heading") or c.get("citation_text") or "") for c in data["citations"])

    # Verify audit ledger entry
    db = SessionLocal()
    ledger_entry = db.query(EvidenceLedger).filter(EvidenceLedger.id == data["ledger_id"]).first()
    assert ledger_entry is not None
    assert ledger_entry.policy_id == elena_policy_id
    assert ledger_entry.outcome == "answered"
    db.close()


def test_what_policies_does_elena_moreau_have_portfolio():
    """Test 'What policies does Elena Moreau have?' answers from portfolio listing without confusion."""
    conv_resp = client.post("/api/conversations")
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What policies does Elena Moreau have?"},
    )
    assert q_resp.status_code == 201
    data = q_resp.json()

    assert data["status"] == "answered"
    assert data["answer_type"] == "portfolio"
    assert "HO-9021-4477" in data["answer"]
    assert "PA-8830-2215" in data["answer"]
    assert data["portfolio"]["scope"] == "customer"
    assert len(data["portfolio"]["policies"]) == 2


def test_what_policy_does_elena_moreau_have_singular():
    """Test singular 'What policy does Elena Moreau have?' routes to portfolio."""
    conv_resp = client.post("/api/conversations")
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What policy does Elena Moreau have?"},
    )
    assert q_resp.status_code == 201
    data = q_resp.json()

    assert data["status"] == "answered"
    assert data["answer_type"] == "portfolio"
    assert "HO-9021-4477" in data["answer"]
    assert "PA-8830-2215" in data["answer"]


def test_what_policy_do_we_have_without_selected_policy():
    """Test 'What policy do we have?' without an active policy routes to book/portfolio."""
    conv_resp = client.post("/api/conversations")
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What policy do we have?"},
    )
    assert q_resp.status_code == 201
    data = q_resp.json()

    assert data["status"] == "answered"
    assert data["answer_type"] == "portfolio"


def test_policy_metadata_specific_questions(elena_policy_id):
    """Test specific policy metadata questions: number, effective dates, status."""
    conv_resp = client.post("/api/conversations", json={"policy_id": elena_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    # 1. Policy number
    r_num = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What is the policy number?"},
    )
    assert r_num.status_code == 201
    data_num = r_num.json()
    assert data_num["status"] == "answered"
    assert "HO-9021-4477" in data_num["answer"]
    assert any(e["source_type"] == "policy_meta" for e in data_num["evidence"])

    # 2. Effective dates
    r_dates = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What are the policy's effective dates?"},
    )
    assert r_dates.status_code == 201
    data_dates = r_dates.json()
    assert data_dates["status"] == "answered"
    assert "2025" in data_dates["answer"] or "November" in data_dates["answer"]
    assert any(e["source_type"] == "policy_meta" for e in data_dates["evidence"])

    # 3. Policy status
    r_status = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What is the status of this policy?"},
    )
    assert r_status.status_code == 201
    data_status = r_status.json()
    assert data_status["status"] == "answered"
    assert "in force" in data_status["answer"].lower() or "in_force" in data_status["answer"].lower()


def test_coverage_and_deductible_questions_continue_to_work(elena_policy_id):
    """Ensure specific coverage & deductible questions continue to retrieve coverage & clause records."""
    conv_resp = client.post("/api/conversations", json={"policy_id": elena_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What are the limits and deductible for Coverage A — Dwelling?"},
    )
    assert q_resp.status_code == 201
    data = q_resp.json()
    assert data["status"] == "answered"
    assert data["guardrail_status"] == "passed"
    assert len(data["evidence"]) >= 1
    # Evidence must come from clause or coverage, not policy_meta
    source_types = {e["source_type"] for e in data["evidence"]}
    assert "clause" in source_types or "coverage" in source_types
    assert "890,000" in data["answer"] or "890000" in data["answer"]


def test_unsupported_questions_return_insufficient_evidence(elena_policy_id):
    """Unsupported questions must safely return insufficient evidence and not synthesize fake answers."""
    conv_resp = client.post("/api/conversations", json={"policy_id": elena_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "Does this policy cover damage from a nuclear war?"},
    )
    assert q_resp.status_code == 201
    data = q_resp.json()
    assert data["status"] == "insufficient_evidence"
    assert data["confidence"] == "none"
    assert data["guardrail_status"] == "no_evidence"
    assert len(data["evidence"]) == 0
    assert "couldn't find sufficient policy evidence" in data["answer"].lower()

    # Verify audit ledger records insufficient_evidence status
    db = SessionLocal()
    ledger_entry = db.query(EvidenceLedger).filter(EvidenceLedger.id == data["ledger_id"]).first()
    assert ledger_entry is not None
    assert ledger_entry.outcome == "insufficient_evidence"
    assert ledger_entry.guardrail_status == "no_evidence"
    db.close()
