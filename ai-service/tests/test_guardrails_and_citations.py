"""Unit tests for inline evidence references, citation building and guardrail checks."""

import os
import sys

ai_service_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ai_service_dir not in sys.path:
    sys.path.insert(0, ai_service_dir)

from app.services.explainer_pipeline import _grade_confidence, retrieval_query
from app.services.guardrails.validator import GuardrailValidator
from app.services.llm.base import (
    citations_from_references,
    normalize_evidence_references,
    referenced_evidence_indexes,
)
from app.services.retrieval.evidence_retriever import EvidenceItem


def _evidence():
    return [
        EvidenceItem(
            source_type="clause", source_id="c1", title="Clause: Water Back-Up", content="We cover water back-up.",
            form_number="HO 04 95", edition="10 00", page=1, heading="Water Back-Up", relevance_score=30.0,
            metadata={"scope": "customer_form"},
        ),
        EvidenceItem(
            source_type="coverage", source_id="cov1", title="Coverage: Water Back-Up", content="Limit $10,000",
            form_number="HO 04 95", relevance_score=25.0,
        ),
        EvidenceItem(
            source_type="coverage", source_id="cov2", title="Coverage: Coverage A", content="Limit $512,000",
            form_number="HO 00 03", relevance_score=10.0,
        ),
    ]


def _check(result, name):
    return next(c for c in result.checks if c["name"] == name)


def test_normalize_references_handles_model_variants():
    raw = "Covered [​E1] up to $10,000 [E2, E3] and [ E1 ]."
    assert normalize_evidence_references(raw) == "Covered [E1] up to $10,000 [E2][E3] and [E1]."


def test_normalize_folds_non_breaking_typography():
    assert normalize_evidence_references("water‑back‑up cover") == "water-back-up cover"


def test_referenced_indexes_in_first_use_order():
    assert referenced_evidence_indexes("a [E3] b [E1][E3] c [E2]") == [3, 1, 2]


def test_citations_only_for_referenced_evidence():
    cites = citations_from_references("Covered [E2].", _evidence())
    assert [c["source_id"] for c in cites] == ["cov1"]
    assert cites[0]["evidence_index"] == 2


def test_coverage_citations_sharing_a_form_are_not_merged():
    cites = citations_from_references("A [E2] and B [E3].", _evidence())
    assert [c["source_id"] for c in cites] == ["cov1", "cov2"]


def test_guardrails_pass_grounded_answer():
    ev = _evidence()
    answer = "Water back-up is covered up to **$10,000** [E1][E2]."
    result = GuardrailValidator.validate(answer, citations_from_references(answer, ev), ev, policy_number="HO-2847-1193")
    assert result.status == "passed"
    assert {c["status"] for c in result.checks} == {"passed"}
    assert {c["name"] for c in result.checks} >= {
        "answer_present", "evidence_grounded", "inline_citations", "citations_verified",
        "cross_policy_leak", "premium_promise", "coverage_determination",
    }


def test_invalid_reference_is_removed_and_reported():
    result = GuardrailValidator.validate("Covered [E1] and [E9].", [], _evidence(), policy_number="HO-2847-1193")
    assert "[E9]" not in result.validated_answer
    assert _check(result, "inline_citations")["status"] == "failed"


def test_premium_promise_is_flagged():
    result = GuardrailValidator.validate("We can lower your premium if you raise the deductible [E1].", [], _evidence(), "HO-2847-1193")
    assert result.status == "flagged"
    assert _check(result, "premium_promise")["status"] == "failed"


def test_cross_policy_leak_is_flagged():
    result = GuardrailValidator.validate("Policy PA-6120-7741 has collision [E1].", [], _evidence(), "HO-2847-1193")
    assert result.status == "flagged"
    assert "PA-6120-7741" in _check(result, "cross_policy_leak")["detail"]


def test_coverage_determination_is_flagged():
    result = GuardrailValidator.validate("Your claim will be paid in full [E1].", [], _evidence(), "HO-2847-1193")
    assert result.status == "flagged"
    assert _check(result, "coverage_determination")["status"] == "failed"


def test_confidence_grading():
    ev = _evidence()
    cites = citations_from_references("[E1][E2]", ev)
    assert _grade_confidence(ev, cites, "passed", has_inline_references=True) == "high"
    assert _grade_confidence(ev, cites, "passed", has_inline_references=False) == "medium"
    assert _grade_confidence(ev, cites, "flagged", has_inline_references=True) == "low"
    assert _grade_confidence([], [], "no_evidence", has_inline_references=False) == "none"


def test_follow_up_questions_inherit_previous_subject():
    previous = "Does Margaret Chen have water backup coverage?"
    assert previous in retrieval_query("What endorsement provides that coverage?", previous)
    assert retrieval_query("What is the deductible?", previous) == "What is the deductible?"


def test_normalize_fullwidth_citation_brackets():
    assert normalize_evidence_references("Not covered \u3010E1\u3011\u3010E2\u3011.") == "Not covered [E1][E2]."


def test_policy_number_is_not_used_as_search_terms():
    from app.services.retrieval.evidence_retriever import POLICY_NUMBER_REFERENCE, _tokenize

    question = "Does HO-2847-1193 cover damage from alien spacecraft?"
    terms = _tokenize(POLICY_NUMBER_REFERENCE.sub(" ", question))
    assert not terms & {"ho", "2847", "1193", "ho-2847-1193"}
    # Form numbers in a question are still searchable.
    assert POLICY_NUMBER_REFERENCE.sub(" ", "What does HO 04 95 cover?") == "What does HO 04 95 cover?"


def test_fallback_answers_are_never_graded_high(monkeypatch):
    """Answers from the deterministic engine are capped at medium confidence."""
    from app.core.config import settings
    from app.services.explainer_pipeline import ExplainerPipeline
    from app.db.database import SessionLocal
    from app.models.policy import CorePolicy

    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")  # no key -> deterministic engine
    db = SessionLocal()
    try:
        policy = db.query(CorePolicy).filter(CorePolicy.policy_number == "HO-2847-1193", CorePolicy.status == "in_force").first()
        result = ExplainerPipeline.process_question("Does this policy have water backup coverage?", policy.id, db)
    finally:
        db.close()
    assert result.is_fallback is True
    assert result.confidence in ("medium", "low")
    assert "No API key configured" in (result.fallback_reason or "")
