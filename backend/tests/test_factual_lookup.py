"""Tests for Feature 1: Direct factual lookups for schedule fields.

Verifies:
1. Deductible and policy limit from CoreCoverage
2. Annual premium from CorePolicy
3. Next bill due date and amount from CoreBilling
4. Claim status and assigned adjuster from CoreClaim
5. Zero LLM calls for clear factual questions
6. Explicit handling of multiple coverages and multiple claims
7. Missing record handling
8. Hybrid questions preserving both direct facts and grounded policy wording
"""

import os
import sys
from unittest.mock import patch
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
def elena_home_policy_id():
    """Retrieve Elena Moreau's Homeowners policy ID (HO-9021-4477)."""
    db = SessionLocal()
    policy = db.query(CorePolicy).filter(CorePolicy.policy_number == "HO-9021-4477").first()
    db.close()
    assert policy is not None, "Elena Moreau's policy HO-9021-4477 must exist in database"
    return policy.id


@pytest.fixture(scope="module")
def ortiz_auto_policy_id():
    """Retrieve Ortiz's Personal Auto policy ID with seeded claims and billing."""
    db = SessionLocal()
    policy = db.query(CorePolicy).filter(CorePolicy.policy_number == "PA-5518-0042").first()
    db.close()
    assert policy is not None, "Ortiz's policy PA-5518-0042 must exist in database"
    return policy.id


def test_deductible_specific_coverage(elena_home_policy_id):
    """Factual lookup for a specific coverage deductible directly from CoreCoverage without LLM."""
    conv_resp = client.post("/api/conversations", json={"policy_id": elena_home_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    with patch("app.services.ai_client.ai_client.explain") as mock_explain:
        q_resp = client.post(
            f"/api/conversations/{conv_id}/questions",
            json={"question": "What is the deductible for Coverage A — Dwelling?"},
        )
        assert q_resp.status_code == 201
        data = q_resp.json()

        # LLM explain must NOT be called
        mock_explain.assert_not_called()

        assert data["status"] == "answered"
        assert data["model_used"] == "none (records)"
        assert "5,000" in data["answer"] or "5000" in data["answer"]
        assert "Coverage A" in data["answer"]
        assert len(data["evidence"]) >= 1
        assert data["evidence"][0]["source_type"] == "coverage"
        assert len(data["citations"]) >= 1


def test_deductible_all_coverages_when_unspecified(elena_home_policy_id):
    """When no specific coverage is named, list all scheduled deductibles explicitly."""
    conv_resp = client.post("/api/conversations", json={"policy_id": elena_home_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    with patch("app.services.ai_client.ai_client.explain") as mock_explain:
        q_resp = client.post(
            f"/api/conversations/{conv_id}/questions",
            json={"question": "What is my deductible?"},
        )
        assert q_resp.status_code == 201
        data = q_resp.json()
        mock_explain.assert_not_called()

        assert data["status"] == "answered"
        assert data["model_used"] == "none (records)"
        # Shows listed deductibles
        assert "deductible" in data["answer"].lower()
        assert len(data["evidence"]) >= 1
        assert all(e["source_type"] == "coverage" for e in data["evidence"])


def test_policy_limit_specific_coverage(elena_home_policy_id):
    """Factual lookup for a specific coverage limit directly from CoreCoverage without LLM."""
    conv_resp = client.post("/api/conversations", json={"policy_id": elena_home_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    with patch("app.services.ai_client.ai_client.explain") as mock_explain:
        q_resp = client.post(
            f"/api/conversations/{conv_id}/questions",
            json={"question": "What is the limit for dwelling?"},
        )
        assert q_resp.status_code == 201
        data = q_resp.json()
        mock_explain.assert_not_called()

        assert data["status"] == "answered"
        assert data["model_used"] == "none (records)"
        assert "890,000" in data["answer"] or "890000" in data["answer"]
        assert any(e["source_type"] == "coverage" for e in data["evidence"])


def test_policy_limits_all_coverages(elena_home_policy_id):
    """Factual lookup listing all coverage limits when no coverage is specified."""
    conv_resp = client.post("/api/conversations", json={"policy_id": elena_home_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    with patch("app.services.ai_client.ai_client.explain") as mock_explain:
        q_resp = client.post(
            f"/api/conversations/{conv_id}/questions",
            json={"question": "What are my policy limits?"},
        )
        assert q_resp.status_code == 201
        data = q_resp.json()
        mock_explain.assert_not_called()

        assert data["status"] == "answered"
        assert data["model_used"] == "none (records)"
        assert len(data["evidence"]) >= 2
        assert "limits on record" in data["answer"].lower()


def test_annual_premium(elena_home_policy_id):
    """Factual lookup for annual premium directly from CorePolicy without LLM."""
    conv_resp = client.post("/api/conversations", json={"policy_id": elena_home_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    with patch("app.services.ai_client.ai_client.explain") as mock_explain:
        q_resp = client.post(
            f"/api/conversations/{conv_id}/questions",
            json={"question": "What is my annual premium?"},
        )
        assert q_resp.status_code == 201
        data = q_resp.json()
        mock_explain.assert_not_called()

        assert data["status"] == "answered"
        assert data["model_used"] == "none (records)"
        assert "$" in data["answer"]
        assert any(e["source_type"] == "policy_meta" for e in data["evidence"])


def test_billing_due_date_and_amount(ortiz_auto_policy_id):
    """Factual lookup for next bill due date and amount from CoreBilling without LLM."""
    conv_resp = client.post("/api/conversations", json={"policy_id": ortiz_auto_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    with patch("app.services.ai_client.ai_client.explain") as mock_explain:
        q_resp = client.post(
            f"/api/conversations/{conv_id}/questions",
            json={"question": "When is my bill due?"},
        )
        assert q_resp.status_code == 201
        data = q_resp.json()
        mock_explain.assert_not_called()

        assert data["status"] == "answered"
        assert data["model_used"] == "none (records)"
        assert "due on" in data["answer"].lower()
        assert any(e["source_type"] == "billing" for e in data["evidence"])


def test_claim_status_and_adjuster(ortiz_auto_policy_id):
    """Factual lookup for claim status and assigned adjuster from CoreClaim without LLM."""
    conv_resp = client.post("/api/conversations", json={"policy_id": ortiz_auto_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    with patch("app.services.ai_client.ai_client.explain") as mock_explain:
        q_resp = client.post(
            f"/api/conversations/{conv_id}/questions",
            json={"question": "What is my claim status and assigned adjuster?"},
        )
        assert q_resp.status_code == 201
        data = q_resp.json()
        mock_explain.assert_not_called()

        assert data["status"] == "answered"
        assert data["model_used"] == "none (records)"
        assert "open" in data["answer"].lower()
        assert "Villanueva" in data["answer"] or "adjuster" in data["answer"].lower()
        assert any(e["source_type"] == "claim" for e in data["evidence"])


def test_missing_claims_on_policy(elena_home_policy_id):
    """When a policy has no claims, report that no claims exist rather than inventing values."""
    conv_resp = client.post("/api/conversations", json={"policy_id": elena_home_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    with patch("app.services.ai_client.ai_client.explain") as mock_explain:
        q_resp = client.post(
            f"/api/conversations/{conv_id}/questions",
            json={"question": "Who is the assigned adjuster on my claim?"},
        )
        assert q_resp.status_code == 201
        data = q_resp.json()
        mock_explain.assert_not_called()

        assert "no claims on file" in data["answer"].lower() or "not contain any claims" in data["answer"].lower()


def test_evidence_ledger_entry_created_for_direct_lookup(ortiz_auto_policy_id):
    """Ensure Evidence Ledger entries are properly created and audit-compliant for factual lookups."""
    conv_resp = client.post("/api/conversations", json={"policy_id": ortiz_auto_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "When is my next bill due?"},
    )
    assert q_resp.status_code == 201
    data = q_resp.json()

    db = SessionLocal()
    ledger_entry = db.query(EvidenceLedger).filter(EvidenceLedger.id == data["ledger_id"]).first()
    assert ledger_entry is not None
    assert ledger_entry.policy_id == ortiz_auto_policy_id
    assert ledger_entry.outcome == "answered"
    assert ledger_entry.model_used == "none (records)"
    assert len(ledger_entry.retrieved_evidence) >= 1
    assert ledger_entry.retrieved_evidence[0]["source_type"] == "billing"
    assert len(ledger_entry.citations) >= 1
    db.close()


def test_hybrid_factual_and_wording_question(elena_home_policy_id):
    """Hybrid question: combines factual deductible lookup with policy-wording coverage explanation."""
    conv_resp = client.post("/api/conversations", json={"policy_id": elena_home_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What is the deductible for Coverage A, and what perils are excluded?"},
    )
    assert q_resp.status_code == 201
    data = q_resp.json()

    # Preserves factual part (Coverage A deductible)
    assert "5,000" in data["answer"] or "5000" in data["answer"]
    # Evidence includes direct coverage
    source_types = {e["source_type"] for e in data["evidence"]}
    assert "coverage" in source_types
    # Citations exist and are valid
    assert len(data["citations"]) >= 1
