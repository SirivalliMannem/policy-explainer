"""Evidence Ledger service for logging and traceability."""

from __future__ import annotations

from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.ledger import EvidenceLedger


def answer_outcome(question_status: str, guardrail_status: str) -> str:
    """Classify what happened to a question for the audit record.

    answered              grounded answer delivered with all blocking guardrails passed
    insufficient_evidence no policy evidence matched; nothing was generated
    needs_review          an answer exists but a blocking guardrail failed, so a person must review it
    """
    if question_status == "insufficient_evidence":
        return "insufficient_evidence"
    if guardrail_status in ("flagged", "failed"):
        return "needs_review"
    return "answered"


class LedgerService:
    """Records audit trail of question, retrieved evidence, grounding, and answer into EvidenceLedger."""

    @staticmethod
    def record_entry(
        conversation_id: str,
        question_id: str,
        policy_id: Optional[str],
        question: str,
        evidence: list[Any],
        grounding_context: str,
        raw_llm_response: str,
        final_answer: str,
        citations: list[dict],
        confidence: str,
        guardrail_status: str,
        suggested_questions: list[str],
        db: Session,
        employee_id: Optional[str] = None,
        outcome: Optional[str] = None,
        guardrail_checks: Optional[list[dict]] = None,
        model_used: Optional[str] = None,
        provider: Optional[str] = None,
        is_fallback: Optional[bool] = None,
        fallback_reason: Optional[str] = None,
        latency_ms: Optional[int] = None,
        timings_ms: Optional[dict] = None,
        retrieval: Optional[dict] = None,
    ) -> EvidenceLedger:
        """Create and persist an evidence ledger entry."""
        evidence_dicts: list[dict[str, Any]] = []
        for item in evidence:
            if hasattr(item, "model_dump"):
                evidence_dicts.append(item.model_dump())
            elif isinstance(item, dict):
                evidence_dicts.append(item)
            else:
                evidence_dicts.append(
                    {
                        "source_type": getattr(item, "source_type", ""),
                        "source_id": getattr(item, "source_id", ""),
                        "title": getattr(item, "title", ""),
                        "content": getattr(item, "content", ""),
                        "form_number": getattr(item, "form_number", None),
                        "edition": getattr(item, "edition", None),
                        "page": getattr(item, "page", None),
                        "section": getattr(item, "section", None),
                        "heading": getattr(item, "heading", None),
                        "plain_language": getattr(item, "plain_language", None),
                        "relevance_score": getattr(item, "relevance_score", 1.0),
                        "metadata": getattr(item, "metadata", {}),
                    }
                )

        ledger_entry = EvidenceLedger(
            conversation_id=conversation_id,
            question_id=question_id,
            policy_id=policy_id,
            question=question,
            retrieved_evidence=evidence_dicts,
            grounding_context=grounding_context,
            raw_llm_response=raw_llm_response,
            final_answer=final_answer,
            citations=citations,
            confidence=confidence,
            guardrail_status=guardrail_status,
            suggested_questions=suggested_questions,
            employee_id=employee_id,
            outcome=outcome,
            guardrail_checks=guardrail_checks or [],
            model_used=model_used,
            provider=provider,
            is_fallback=is_fallback,
            fallback_reason=fallback_reason,
            latency_ms=latency_ms,
            timings_ms=timings_ms or {},
            retrieval=retrieval or {},
        )
        db.add(ledger_entry)
        db.commit()
        db.refresh(ledger_entry)
        return ledger_entry
