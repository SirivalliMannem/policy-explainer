"""Coordinating pipeline for the AI Policy Explainer in the AI microservice."""

from __future__ import annotations

from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.policy import CorePolicy
from app.schemas.explain import (
    CitationItem,
    EvidenceItemSchema,
    ExplainResponse,
)
from app.schemas.policy_context import PolicyContextSummary
from app.services.grounding.context_builder import GroundingContextBuilder
from app.services.guardrails.validator import GuardrailValidator
from app.services.llm.llm_service import LLMService
from app.services.retrieval.evidence_retriever import EvidenceRetriever
from app.services.suggestions.generator import SuggestionGenerator


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
    ) -> ExplainResponse:
        """Execute full Explainer pipeline for a policy question."""
        policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first()
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Policy with ID '{policy_id}' not found",
            )

        customer = policy.account

        # 1. Retrieve relevant evidence grounded in policy
        evidence = EvidenceRetriever.retrieve(question, policy.id, db)

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
                grounding_context="No evidence retrieved",
                raw_llm_response="",
            )

        # 2. Build grounding context
        grounding_context = GroundingContextBuilder.build(
            question=question,
            policy=policy,
            customer=customer,
            evidence=evidence,
        )

        # 3. Generate answer via LLM service (or deterministic grounded synthesizer)
        llm_result = LLMService.generate_answer(
            question=question,
            grounding_context=grounding_context,
            evidence=evidence,
        )

        # 4. Guardrail & Citation validation
        guardrail_result = GuardrailValidator.validate(
            answer=llm_result.answer,
            citations=llm_result.citations,
            evidence=evidence,
        )

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
            )
            for item in evidence
        ]

        citation_schemas = [
            CitationItem(
                source_id=c.get("source_id"),
                form_number=c.get("form_number"),
                edition=c.get("edition"),
                page=c.get("page"),
                section=c.get("section"),
                heading=c.get("heading"),
                citation_text=c.get("citation_text"),
            )
            for c in verified_citations
        ]

        return ExplainResponse(
            question=question,
            answer=final_answer,
            confidence=llm_result.confidence,
            status="answered",
            evidence=evidence_schemas,
            citations=citation_schemas,
            suggested_questions=suggestions,
            guardrail_status=guardrail_result.status,
            grounding_context=grounding_context,
            raw_llm_response=llm_result.raw_response,
        )
