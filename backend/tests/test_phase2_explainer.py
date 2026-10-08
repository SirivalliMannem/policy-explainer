"""Phase 2 AI Policy Explainer backend test suite.

Validates all 12 required test scenarios plus database safety and Backend -> AI Service communication.
"""

import sys
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# Ensure backend directory is in python path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.db.database import get_db, SessionLocal, engine
from app.models.ledger import EvidenceLedger
from app.services.ai_client import ai_client, AIServiceClient
from app.schemas.explainer import AIServiceResponse


client = TestClient(app)

BASELINE_COUNTS = {
    "core_account": 6,
    "core_policy": 10,
    "core_coverage": 43,
    "core_form": 24,
    "core_billing": 9,
    "core_claim": 1,
    "clause": 234,
    "golden_question": 14,
    "knowledge_collection": 5,
    "knowledge_document": 12,
}


@pytest.fixture(scope="session", autouse=True)
def ensure_ai_service():
    """Ensure the AI microservice daemon is running on port 8001 during test suite execution."""
    import httpx, subprocess, time
    # Check if AI service is already running on port 8001
    try:
        r = httpx.get("http://127.0.0.1:8001/health", timeout=0.5)
        if r.status_code == 200:
            yield
            return
    except Exception:
        pass

    # Start AI service in a background subprocess
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ai_dir = os.path.join(root_dir, "ai-service")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8001", "--host", "127.0.0.1"],
        cwd=ai_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for service to be healthy
    started = False
    for _ in range(30):
        time.sleep(0.2)
        try:
            r = httpx.get("http://127.0.0.1:8001/health", timeout=0.5)
            if r.status_code == 200:
                started = True
                break
        except Exception:
            pass

    if not started:
        proc.kill()
        raise RuntimeError("Failed to start AI service on port 8001 for test execution")

    try:
        yield
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3.0)
        except Exception:
            proc.kill()


@pytest.fixture(scope="session")
def seeded_policy_id():
    """Retrieve Margaret Chen's Homeowners policy ID for testing."""
    response = client.get("/api/policy-resolution/search?q=HO-2847")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    return data[0]["policy_id"]


def test_01_policy_specific_coverage_question(seeded_policy_id):
    """Scenario 1: Policy-specific coverage question: Does this policy have water backup coverage?"""
    # 1. Create conversation with Margaret Chen's policy
    conv_resp = client.post("/api/conversations", json={"policy_id": seeded_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    # 2. Ask question
    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "Does this policy have water backup coverage?"},
    )
    assert q_resp.status_code == 201
    data = q_resp.json()

    # Validate response structure
    assert data["conversation_id"] == conv_id
    assert "question_id" in data
    assert data["question"] == "Does this policy have water backup coverage?"
    assert len(data["answer"]) > 0
    assert "water back-up" in data["answer"].lower() or "water backup" in data["answer"].lower()
    assert data["confidence"] in ["high", "medium"]
    assert data["status"] == "answered"

    # Validate evidence returned
    assert len(data["evidence"]) > 0
    first_ev = data["evidence"][0]
    assert "source_type" in first_ev
    assert "title" in first_ev

    # Validate citations
    assert len(data["citations"]) > 0

    # Validate suggested questions
    assert 0 <= len(data["suggested_questions"]) <= 3


def test_02_deductible_question(seeded_policy_id):
    """Scenario 2: Deductible question: What is the deductible for this policy?"""
    conv_resp = client.post("/api/conversations", json={"policy_id": seeded_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What is the deductible for this policy?"},
    )
    assert q_resp.status_code == 201
    data = q_resp.json()

    assert data["status"] == "answered"
    assert "deductible" in data["answer"].lower()
    assert len(data["evidence"]) > 0
    assert 0 <= len(data["suggested_questions"]) <= 3


def test_03_form_endorsement_question(seeded_policy_id):
    """Scenario 3: Form/endorsement question: Which endorsement provides water backup coverage?"""
    conv_resp = client.post("/api/conversations", json={"policy_id": seeded_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "Which endorsement provides water backup coverage?"},
    )
    assert q_resp.status_code == 201
    data = q_resp.json()

    assert data["status"] == "answered"
    assert any(
        "ho 04 95" in str(c.get("form_number") or "").lower()
        or "ho 04 95" in data["answer"].lower()
        for c in data["citations"]
    ) or "04 95" in data["answer"]


def test_04_insufficient_evidence_question(seeded_policy_id):
    """Scenario 4: Question where evidence is insufficient (e.g. extraterrestrial/unsupported)."""
    conv_resp = client.post("/api/conversations", json={"policy_id": seeded_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "Does this policy cover damage from alien spacecraft abductions or Martian UFO sightings?"},
    )
    assert q_resp.status_code == 201
    data = q_resp.json()

    assert data["status"] in ["insufficient_evidence", "answered"]
    assert "insufficient" in data["answer"].lower() or "couldn't find" in data["answer"].lower() or "not establish" in data["answer"].lower()


def test_05_question_without_policy_context():
    """Scenario 5: Question submitted to conversation without resolved policy context."""
    conv_resp = client.post("/api/conversations", json={})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What is my deductible?"},
    )
    assert q_resp.status_code == 400
    assert "policy context" in q_resp.json()["detail"].lower()


def test_06_invalid_conversation():
    """Scenario 6: Question submitted to invalid/non-existent conversation ID."""
    q_resp = client.post(
        "/api/conversations/00000000-0000-0000-0000-000000000000/questions",
        json={"question": "What is my deductible?"},
    )
    assert q_resp.status_code == 404
    assert "conversation not found" in q_resp.json()["detail"].lower()


def test_07_backend_to_ai_service_communication(seeded_policy_id):
    """Scenario 7: Directly test Backend -> AI Service communication contract."""
    ai_resp = ai_client.explain(
        question="Does this policy have water backup coverage?",
        policy_id=seeded_policy_id,
        conversation_id="conv-direct-test",
    )
    assert isinstance(ai_resp, AIServiceResponse)
    assert ai_resp.status == "answered"
    assert len(ai_resp.answer) > 0
    assert len(ai_resp.evidence) > 0
    assert len(ai_resp.citations) > 0
    assert ai_resp.guardrail_status == "passed"
    assert len(ai_resp.grounding_context) > 0


def test_08_backend_to_ai_service_insufficient_evidence(seeded_policy_id):
    """Scenario 8: Test Backend -> AI Service communication with unmatchable question."""
    ai_resp = ai_client.explain(
        question="Does this policy cover damage from alien spacecraft abductions or Martian UFO sightings?",
        policy_id=seeded_policy_id,
    )
    assert isinstance(ai_resp, AIServiceResponse)
    assert ai_resp.status == "insufficient_evidence"
    assert ai_resp.confidence == "none"
    assert len(ai_resp.evidence) == 0
    assert "couldn't find" in ai_resp.answer.lower() or "insufficient" in ai_resp.answer.lower()


def test_09_backend_ai_client_invalid_policy():
    """Scenario 9: Test Backend -> AI Service error handling for non-existent policy."""
    with pytest.raises(Exception) as excinfo:
        ai_client.explain(
            question="What is the deductible?",
            policy_id="00000000-0000-0000-0000-000000000000",
        )
    assert "404" in str(excinfo.value) or "not found" in str(excinfo.value).lower()


def test_10_conversation_continuity(seeded_policy_id):
    """Scenario 10: Multi-turn questions within the same conversation without re-selecting policy."""
    conv_resp = client.post("/api/conversations", json={"policy_id": seeded_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    # Question 1: Coverage
    q1 = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "Does this policy have water backup coverage?"},
    )
    assert q1.status_code == 201
    assert q1.json()["status"] == "answered"

    # Question 2: Deductible (same conversation, no context re-selection)
    q2 = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What is the deductible?"},
    )
    assert q2.status_code == 201
    assert q2.json()["status"] == "answered"

    # Question 3: Endorsement (same conversation)
    q3 = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "What endorsement provides it?"},
    )
    assert q3.status_code == 201
    assert q3.json()["status"] == "answered"

    # Verify history has 3 questions in order
    hist_resp = client.get(f"/api/conversations/{conv_id}/questions")
    assert hist_resp.status_code == 200
    history = hist_resp.json()
    assert len(history) == 3
    assert history[0]["question"] == "Does this policy have water backup coverage?"
    assert history[1]["question"] == "What is the deductible?"
    assert history[2]["question"] == "What endorsement provides it?"


def test_11_evidence_ledger_persisted(seeded_policy_id):
    """Scenario 11: Verify Evidence Ledger records are created with complete audit trail."""
    conv_resp = client.post("/api/conversations", json={"policy_id": seeded_policy_id})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["conversation_id"]

    q_resp = client.post(
        f"/api/conversations/{conv_id}/questions",
        json={"question": "Does this policy have water backup coverage?"},
    )
    assert q_resp.status_code == 201
    question_id = q_resp.json()["question_id"]

    db = SessionLocal()
    try:
        ledger_entry = (
            db.query(EvidenceLedger)
            .filter(EvidenceLedger.question_id == question_id)
            .first()
        )
        assert ledger_entry is not None
        assert ledger_entry.conversation_id == conv_id
        assert ledger_entry.policy_id == seeded_policy_id
        assert ledger_entry.question == "Does this policy have water backup coverage?"
        assert ledger_entry.final_answer == q_resp.json()["answer"]
        assert ledger_entry.guardrail_status == "passed"
        assert len(ledger_entry.grounding_context) > 0
        assert isinstance(ledger_entry.retrieved_evidence, list)
    finally:
        db.close()


def test_12_phase_1_endpoints_continue_working(seeded_policy_id):
    """Scenario 12: Verify all Phase 1 endpoints still function correctly."""
    # Health checks
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r = client.get("/health/db")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # Customers
    r = client.get("/api/customers")
    assert r.status_code == 200
    customers = r.json()
    assert len(customers) > 0
    customer_id = customers[0]["id"]

    r = client.get(f"/api/customers/{customer_id}")
    assert r.status_code == 200

    r = client.get(f"/api/customers/{customer_id}/policies")
    assert r.status_code == 200

    # Policy resolution
    r = client.get("/api/policy-resolution/search?q=HO-2847")
    assert r.status_code == 200

    r = client.post("/api/policy-resolution/resolve", json={"policy_id": seeded_policy_id})
    assert r.status_code == 200
    assert r.json()["policy_id"] == seeded_policy_id

    # Policy sub-resources
    r = client.get(f"/api/policies/{seeded_policy_id}")
    assert r.status_code == 200

    r = client.get(f"/api/policies/{seeded_policy_id}/coverages")
    assert r.status_code == 200

    r = client.get(f"/api/policies/{seeded_policy_id}/forms")
    assert r.status_code == 200

    r = client.get(f"/api/policies/{seeded_policy_id}/claims")
    assert r.status_code == 200

    r = client.get(f"/api/policies/{seeded_policy_id}/billing")
    assert r.status_code == 200


def test_13_database_safety_row_counts_unchanged():
    """Verify seeded database row counts remain exactly unchanged."""
    with engine.connect() as conn:
        for table_name, expected_count in BASELINE_COUNTS.items():
            actual_count = conn.execute(text(f"SELECT count(*) FROM {table_name}")).scalar()
            assert (
                actual_count == expected_count
            ), f"Table {table_name} count changed: expected {expected_count}, got {actual_count}"
