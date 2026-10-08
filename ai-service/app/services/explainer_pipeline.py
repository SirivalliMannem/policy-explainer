"""Coordinating pipeline for the AI Policy Explainer in the AI microservice."""

from __future__ import annotations

import re
import time
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.policy import CorePolicy
from app.schemas.explain import (
    CitationItem,
    EvidenceItemSchema,
    ExplainResponse,
    GuardrailCheck,
)
from app.schemas.policy_context import PolicyContextSummary
from app.services.grounding.context_builder import GroundingContextBuilder
from app.services.guardrails.validator import GuardrailValidator
from app.services.llm.base import citations_from_references
from app.services.llm.llm_service import LLMService
from app.services.retrieval.evidence_retriever import EvidenceItem, EvidenceRetriever
from app.services.suggestions.generator import SuggestionGenerator
from app.core.config import settings
from app.services.understanding import Interpretation, QueryInterpreter
from app.services.understanding.interpreter import FOLLOW_UP_REFERENCE

# Evidence scoring thresholds used to grade confidence (see EvidenceRetriever scoring).
STRONG_EVIDENCE_SCORE = 12.0

def _interpretation_from(data: Optional[dict]) -> Optional[Interpretation]:
    """Rebuild an interpretation sent by the backend, ignoring anything malformed."""
    if not data:
        return None
    try:
        fields = Interpretation.__dataclass_fields__
        return Interpretation(**{k: v for k, v in data.items() if k in fields})
    except TypeError:
        return None


def retrieval_query(question: str, previous_question: Optional[str]) -> str:
    """Augment a referential follow-up with the prior question so retrieval keeps its subject."""
    if previous_question and FOLLOW_UP_REFERENCE.search(question):
        return f"{question} {previous_question}"
    return question


def _elapsed_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


def _evidence_scope(item: EvidenceItem) -> str:
    if item.source_type == "clause":
        return item.metadata.get("scope") or "customer_form"
    # Coverages, forms, claims and billing rows all belong to the resolved policy itself.
    return "policy_record"


def _grade_confidence(
    evidence: list[EvidenceItem],
    verified_citations: list[dict],
    guardrail_status: str,
    has_inline_references: bool,
) -> str:
    """Grade confidence from retrieval strength, citation verification and guardrail outcome."""
    if not evidence:
        return "none"
    if guardrail_status != "passed" or not verified_citations:
        return "low"
    top_score = max(item.relevance_score for item in evidence)
    if top_score >= STRONG_EVIDENCE_SCORE and len(verified_citations) >= 2 and has_inline_references:
        return "high"
    return "medium"


class ExplainerPipeline:
    """End-to-end pipeline executing retrieval, grounding, LLM synthesis, guardrails, and suggestions."""

    @classmethod
    def process_question(
        cls,
        question: str,
        policy_id: str,
        db: Session,
        policy_context: Optional[PolicyContextSummary] = None,
        conversation_id: Optional[str] = None,
        previous_question: Optional[str] = None,
        interpretation: Optional[dict] = None,
    ) -> ExplainResponse:
        """Execute full Explainer pipeline for a policy question."""
        policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first()
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Policy with ID '{policy_id}' not found",
            )

        customer = policy.account
        timings: dict[str, int] = {}

        # 0. Understand the question (spelling, paraphrase, policy vocabulary). Reuse the backend's
        # interpretation when it sent one so the language model is not asked twice.
        interp = _interpretation_from(interpretation)
        if interp is None and settings.QUERY_INTERPRETER.lower() != "off":
            interp = QueryInterpreter.interpret(question, db, previous_question=previous_question)
            timings["interpretation"] = interp.latency_ms
        interpretation_payload = interp.to_dict() if interp else None

        # 1. Retrieve relevant evidence grounded in policy
        started = time.perf_counter()
        search_text = retrieval_query(interp.search_text if interp else question, previous_question)
        evidence, retrieval_stats = EvidenceRetriever.retrieve_with_stats(search_text, policy.id, db)
        retrieval_stats["used_previous_question"] = search_text != question
        timings["retrieval"] = _elapsed_ms(started)

        # Case: Retrieval failure / No evidence
        if not evidence:
            answer_text = "I couldn't find sufficient policy evidence in the current policy to answer that question."
            suggestions = SuggestionGenerator.generate(question, policy, [])

            return ExplainResponse(
                question=question,
                answer=answer_text,
                confidence="none",
                status="insufficient_evidence",
                evidence=[],
                citations=[],
                suggested_questions=suggestions,
                guardrail_status="no_evidence",
                guardrail_checks=[
                    GuardrailCheck(
                        name="evidence_grounded",
                        status="failed",
                        detail="No policy evidence matched the question, so no answer was generated.",
                    )
                ],
                grounding_context="No evidence retrieved",
                raw_llm_response="",
                model_used="none",
                provider="none",
                is_fallback=False,
                retrieval=retrieval_stats,
                timings_ms=timings,
                interpretation=interpretation_payload,
            )

        # 2. Build grounding context
        started = time.perf_counter()
        grounding_context = GroundingContextBuilder.build(
            question=question,
            policy=policy,
            customer=customer,
            evidence=evidence,
            previous_question=previous_question if retrieval_stats["used_previous_question"] else None,
            interpreted_question=interp.corrected if interp and interp.corrected != question else None,
        )
        timings["grounding"] = _elapsed_ms(started)

        # 3. Generate answer via LLM service (or deterministic grounded synthesizer)
        started = time.perf_counter()
        llm_result = LLMService.generate_answer(
            question=question,
            grounding_context=grounding_context,
            evidence=evidence,
        )
        timings["generation"] = _elapsed_ms(started)

        # 4. Guardrail & Citation validation. Prefer citations for the evidence the answer
        # actually references inline; fall back to all citable evidence when it references none.
        started = time.perf_counter()
        referenced = citations_from_references(llm_result.answer, evidence)
        guardrail_result = GuardrailValidator.validate(
            answer=llm_result.answer,
            citations=referenced or llm_result.citations,
            evidence=evidence,
            policy_number=policy.policy_number,
        )
        timings["validation"] = _elapsed_ms(started)

        final_answer = guardrail_result.validated_answer
        verified_citations = guardrail_result.validated_citations

        # 5. Generate contextual suggested questions
        suggestions = SuggestionGenerator.generate(
            question=question,
            policy=policy,
            evidence=evidence,
        )

        # 6. Map to schemas
        evidence_schemas = [
            EvidenceItemSchema(
                source_type=item.source_type,
                source_id=item.source_id,
                title=item.title,
                form_number=item.form_number,
                edition=item.edition,
                page=item.page,
                section=item.section,
                heading=item.heading,
                content=item.content,
                plain_language=item.plain_language,
                relevance_score=item.relevance_score,
                evidence_index=index,
                scope=_evidence_scope(item),
            )
            for index, item in enumerate(evidence, start=1)
        ]

        citation_schemas = [
            CitationItem(
                source_id=c.get("source_id"),
                source_type=c.get("source_type"),
                evidence_index=c.get("evidence_index"),
                form_number=c.get("form_number"),
                edition=c.get("edition"),
                page=c.get("page"),
                section=c.get("section"),
                heading=c.get("heading"),
                citation_text=c.get("citation_text"),
            )
            for c in verified_citations
        ]

        confidence = _grade_confidence(
            evidence,
            verified_citations,
            guardrail_result.status,
            has_inline_references=bool(referenced),
        )
        # The deterministic engine restates the top evidence; it does not reason about the
        # question, so its answers are never graded high.
        if llm_result.is_fallback and confidence == "high":
            confidence = "medium"

        return ExplainResponse(
            question=question,
            answer=final_answer,
            confidence=confidence,
            status="answered",
            evidence=evidence_schemas,
            citations=citation_schemas,
            suggested_questions=suggestions,
            guardrail_status=guardrail_result.status,
            guardrail_checks=[GuardrailCheck(**c) for c in guardrail_result.checks],
            grounding_context=grounding_context,
            raw_llm_response=llm_result.raw_response,
            model_used=llm_result.model_used,
            provider=llm_result.provider,
            is_fallback=llm_result.is_fallback,
            fallback_reason=llm_result.fallback_reason,
            retrieval=retrieval_stats,
            timings_ms=timings,
            interpretation=interpretation_payload,
        )
