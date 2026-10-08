"""Tests for the dedicated AI Service microservice."""

import re
import sys
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# Ensure ai-service directory is in python path
ai_service_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ai_service_dir not in sys.path:
    sys.path.insert(0, ai_service_dir)

from app.main import app
from app.db.database import SessionLocal
from app.models.policy import CorePolicy

client = TestClient(app)


@pytest.fixture(scope="session")
def seeded_policy_id():
    """Retrieve Margaret Chen's Homeowners policy ID for testing."""
    db = SessionLocal()
    try:
        policy = db.query(CorePolicy).filter(CorePolicy.policy_number.like("%2847%")).first()
        assert policy is not None
        return policy.id
    finally:
        db.close()


def test_ai_service_health():
    """Test AI Service health check endpoint."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "policy-explainer-ai-service"


def test_ai_service_health_db():
    """Test AI Service database connectivity probe."""
    res = client.get("/health/db")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_ai_service_explain_coverage(seeded_policy_id):
    """Test AI Service explain question for water backup coverage."""
    payload = {
        "question": "Does this policy have water backup coverage?",
        "policy_id": seeded_policy_id,
        "conversation_id": "conv-test-123",
    }
    res = client.post("/api/explain", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["question"] == "Does this policy have water backup coverage?"
    assert len(data["answer"]) > 0
    # LLM wording varies ("water backup", "water back-up", "water-back-up"); compare without separators.
    assert "waterbackup" in re.sub(r"[\s\-]", "", data["answer"].lower())
    assert data["confidence"] in ["high", "medium"]
    assert data["status"] == "answered"
    assert len(data["evidence"]) > 0
    assert len(data["citations"]) > 0
    assert 0 <= len(data["suggested_questions"]) <= 3
    assert data["guardrail_status"] == "passed"
    assert len(data["grounding_context"]) > 0


def test_ai_service_explain_insufficient_evidence(seeded_policy_id):
    """Test AI Service explain question with unsupported content."""
    payload = {
        "question": "Does this policy cover damage from alien spacecraft abductions or Martian UFO sightings?",
        "policy_id": seeded_policy_id,
    }
    res = client.post("/api/explain", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "insufficient_evidence"
    assert data["confidence"] == "none"
    assert len(data["evidence"]) == 0
    assert "couldn't find" in data["answer"].lower() or "insufficient" in data["answer"].lower()


def test_ai_service_retrieval_direct(seeded_policy_id):
    """Test EvidenceRetriever directly within AI service."""
    from app.services.retrieval.evidence_retriever import EvidenceRetriever
    db = SessionLocal()
    try:
        evidence = EvidenceRetriever.retrieve("water backup", seeded_policy_id, db)
        assert len(evidence) > 0
        assert any("04 95" in (e.form_number or "") for e in evidence)

        # Unmatchable terms return empty list
        no_evidence = EvidenceRetriever.retrieve("xyznonexistentterm99999999", seeded_policy_id, db)
        assert isinstance(no_evidence, list)
    finally:
        db.close()


def test_ai_service_llm_fallback_synthesis(seeded_policy_id):
    """Test LLMService deterministic grounded fallback synthesis."""
    from app.services.retrieval.evidence_retriever import EvidenceRetriever
    from app.services.llm.llm_service import LLMService, LLMGenerationResult
    db = SessionLocal()
    try:
        evidence = EvidenceRetriever.retrieve("water backup", seeded_policy_id, db)
        assert len(evidence) > 0

        result = LLMService.generate_answer(
            question="Does this policy have water backup coverage?",
            grounding_context="Test grounding context",
            evidence=evidence,
        )
        assert isinstance(result, LLMGenerationResult)
        assert len(result.answer) > 0
        assert result.confidence in ["high", "medium"]
    finally:
        db.close()


def test_ai_service_citation_validation_guardrails(seeded_policy_id):
    """Test GuardrailValidator discards fabricated/hallucinated citations."""
    from app.services.retrieval.evidence_retriever import EvidenceRetriever
    from app.services.guardrails.validator import GuardrailValidator
    db = SessionLocal()
    try:
        evidence = EvidenceRetriever.retrieve("water backup", seeded_policy_id, db)
        assert len(evidence) > 0

        fake_citations = [
            {
                "source_id": "fake-nonexistent-clause-999",
                "form_number": "HO 99 99",
                "edition": "01 99",
                "page": 999,
                "section": "Section Fake",
                "heading": "Fake Heading",
                "citation_text": "Fake citation text",
            }
        ]

        val_result = GuardrailValidator.validate(
            answer="This is a test answer claiming fake coverage.",
            citations=fake_citations,
            evidence=evidence,
        )

        for vc in val_result.validated_citations:
            assert vc.get("source_id") != "fake-nonexistent-clause-999"
    finally:
        db.close()



def test_policy_number_in_question_does_not_create_evidence(seeded_policy_id):
    """Naming the policy must not turn its number into matches against every HO form."""
    res = client.post("/api/explain", json={
        "question": "Does HO-2847-1193 cover damage from alien spacecraft?",
        "policy_id": seeded_policy_id,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "insufficient_evidence"
    assert data["evidence"] == []
