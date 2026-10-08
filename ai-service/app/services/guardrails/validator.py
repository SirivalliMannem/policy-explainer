"""Guardrail and citation validation service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from app.services.retrieval.evidence_retriever import EvidenceItem


@dataclass
class GuardrailValidationResult:
    """Result of guardrail validation checks."""

    is_valid: bool
    status: str  # passed | failed
    validated_answer: str
    validated_citations: list[dict] = field(default_factory=list)
    rejection_reason: Optional[str] = None


class GuardrailValidator:
    """Validates generated answers and citations against retrieved evidence."""

    @classmethod
    def validate(
        cls,
        answer: str,
        citations: list[dict],
        evidence: list[EvidenceItem],
    ) -> GuardrailValidationResult:
        """Execute deterministic guardrail checks on generated answer."""
        if not answer or not answer.strip():
            return GuardrailValidationResult(
                is_valid=False,
                status="failed",
                validated_answer="The available policy information could not establish an answer.",
                validated_citations=[],
                rejection_reason="Empty answer produced",
            )

        # Build allowed source keys from retrieved evidence
        valid_form_numbers = {
            item.form_number.strip().lower() for item in evidence if item.form_number
        }
        valid_headings = {
            item.heading.strip().lower() for item in evidence if item.heading
        }

        # Filter citations to only those present in retrieved evidence
        verified_citations = []
        for cit in citations:
            form_num = (cit.get("form_number") or "").strip().lower()
            heading = (cit.get("heading") or "").strip().lower()

            if form_num and form_num in valid_form_numbers:
                verified_citations.append(cit)
            elif heading and heading in valid_headings:
                verified_citations.append(cit)

        # Check for ungrounded answer when evidence was empty
        if not evidence and not any(
            phrase in answer.lower()
            for phrase in ["not find sufficient", "does not establish", "no specific", "couldn't find"]
        ):
            return GuardrailValidationResult(
                is_valid=False,
                status="failed",
                validated_answer="The available policy information does not contain evidence to answer this question.",
                validated_citations=[],
                rejection_reason="Attempted ungrounded answer without supporting evidence",
            )

        return GuardrailValidationResult(
            is_valid=True,
            status="passed",
            validated_answer=answer.strip(),
            validated_citations=verified_citations,
            rejection_reason=None,
        )
