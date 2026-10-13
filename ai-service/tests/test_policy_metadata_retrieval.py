import os
import sys
import pytest

ai_service_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ai_service_dir not in sys.path:
    sys.path.insert(0, ai_service_dir)

from app.db.database import SessionLocal
from app.models.policy import CorePolicy
from app.services.retrieval.evidence_retriever import EvidenceRetriever
from app.services.understanding import QueryInterpreter
from app.services.guardrails.validator import GuardrailValidator


@pytest.fixture(scope="module")
def elena_policy():
    """Retrieve Elena Moreau's Homeowners policy."""
    db = SessionLocal()
    policy = db.query(CorePolicy).filter(CorePolicy.policy_number == "HO-9021-4477").first()
    db.close()
    assert policy is not None
    return policy


def test_evidence_retriever_policy_meta_for_overview(elena_policy):
    """Test EvidenceRetriever retrieves policy_meta for general policy identification."""
    db = SessionLocal()
    evidence, stats = EvidenceRetriever.retrieve_with_stats("What policy do we have?", elena_policy.id, db)
    db.close()

    assert len(evidence) >= 1
    meta = [e for e in evidence if e.source_type == "policy_meta"]
    assert len(meta) == 1
    assert meta[0].source_id == elena_policy.id
    assert "HO-9021-4477" in meta[0].content
    assert "Homeowners" in meta[0].content
    assert meta[0].heading == f"Policy Record ({elena_policy.policy_number})"
    assert meta[0].relevance_score >= 10.0
    # Query terms must not be empty
    assert len(stats.get("query_terms", [])) > 0


def test_evidence_retriever_policy_meta_for_attributes(elena_policy):
    """Test EvidenceRetriever retrieves policy_meta for specific attribute questions."""
    db = SessionLocal()

    # 1. Policy number
    ev_num, _ = EvidenceRetriever.retrieve_with_stats("What is the policy number?", elena_policy.id, db)
    assert any(e.source_type == "policy_meta" for e in ev_num)

    # 2. Effective dates
    ev_dates, _ = EvidenceRetriever.retrieve_with_stats("What are the policy's effective dates?", elena_policy.id, db)
    assert any(e.source_type == "policy_meta" for e in ev_dates)

    # 3. Status
    ev_stat, _ = EvidenceRetriever.retrieve_with_stats("What is the status of this policy?", elena_policy.id, db)
    assert any(e.source_type == "policy_meta" for e in ev_stat)

    db.close()


def test_evidence_retriever_does_not_match_unsupported_questions(elena_policy):
    """Genuinely unsupported questions must not retrieve policy_meta or any other evidence."""
    db = SessionLocal()
    evidence, stats = EvidenceRetriever.retrieve_with_stats(
        "Does this policy cover damage from a nuclear war?", elena_policy.id, db
    )
    db.close()

    assert len(evidence) == 0


def test_guardrail_validator_verifies_policy_meta_citations(elena_policy):
    """Verify citations referencing policy_meta pass GuardrailValidator."""
    db = SessionLocal()
    evidence, _ = EvidenceRetriever.retrieve_with_stats("What policy do we have?", elena_policy.id, db)
    db.close()

    answer = f"The policy is a Homeowners form with number {elena_policy.policy_number} [E1]."
    citations = [
        {
            "source_id": elena_policy.id,
            "source_type": "policy_meta",
            "evidence_index": 1,
            "heading": f"Policy Record ({elena_policy.policy_number})",
            "citation_text": f"Policy Record ({elena_policy.policy_number})",
        }
    ]

    result = GuardrailValidator.validate(
        answer=answer,
        citations=citations,
        evidence=evidence,
        policy_number=elena_policy.policy_number,
    )

    assert result.is_valid is True
    assert result.status == "passed"
    assert len(result.validated_citations) == 1
