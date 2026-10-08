"""Isolated LLM service supporting configurable LLM providers with deterministic grounded fallback."""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings
from app.services.llm.base import (
    BaseLLMProvider,
    LLMGenerationResult,
    extract_citations_from_evidence,
)
from app.services.llm.exceptions import LLMConfigurationError
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.groq_provider import GroqProvider
from app.services.retrieval.evidence_retriever import EvidenceItem

logger = logging.getLogger(__name__)


class LLMService:
    """Service providing grounded answer synthesis via configurable LLM or deterministic fallback."""

    SUPPORTED_PROVIDERS = ("groq", "gemini")

    @classmethod
    def get_provider(cls, provider_name: Optional[str] = None) -> BaseLLMProvider:
        """Instantiate and return the configured LLM provider instance."""
        target = (provider_name or settings.LLM_PROVIDER or "groq").strip().lower()

        if target == "groq":
            return GroqProvider(
                api_key=settings.GROQ_API_KEY,
                model=settings.GROQ_MODEL,
                base_url=settings.GROQ_BASE_URL,
            )
        elif target == "gemini":
            return GeminiProvider(
                api_key=settings.GEMINI_API_KEY,
                model=settings.GEMINI_MODEL,
                base_url=settings.GEMINI_BASE_URL,
            )
        else:
            raise LLMConfigurationError(
                f"Unsupported LLM provider '{target}'. "
                f"Supported providers are: {', '.join(cls.SUPPORTED_PROVIDERS)}."
            )

    @classmethod
    def validate_configuration(cls, provider_name: Optional[str] = None) -> None:
        """Validate credentials for the currently selected provider."""
        provider = cls.get_provider(provider_name)
        provider.validate_configuration()

    @classmethod
    def generate_answer(
        cls,
        question: str,
        grounding_context: str,
        evidence: list[EvidenceItem],
    ) -> LLMGenerationResult:
        """Generate answer from grounding context via active provider or fallback."""
        if not evidence:
            return LLMGenerationResult(
                answer="I couldn't find sufficient policy evidence in the current policy to answer that question.",
                raw_response="",
                citations=[],
                confidence="none",
                model_used="none",
                is_fallback=True,
            )

        provider = cls.get_provider()

        # If active provider has an API key configured, attempt external model invocation
        if provider.is_configured:
            try:
                result = provider.generate(question, grounding_context, evidence)
                if result:
                    return result
            except Exception as e:
                # Never log raw sensitive API keys or auth headers
                logger.warning(
                    "%s LLM invocation failed; engaging deterministic grounded fallback: %s",
                    provider.name.capitalize(),
                    str(e),
                )
        else:
            logger.info(
                "Active provider '%s' has no API key configured; engaging deterministic grounded fallback",
                provider.name,
            )

        # Deterministic grounded synthesizer (approved policy wording & coverage facts)
        return cls._synthesize_grounded_answer(question, evidence)

    @classmethod
    def _synthesize_grounded_answer(
        cls,
        question: str,
        evidence: list[EvidenceItem],
    ) -> LLMGenerationResult:
        """Deterministic grounded synthesizer using approved carrier plain-language wording."""
        cov_items = [e for e in evidence if e.source_type == "coverage"]
        clause_items = [e for e in evidence if e.source_type == "clause"]
        form_items = [e for e in evidence if e.source_type == "form"]
        claim_items = [e for e in evidence if e.source_type == "claim"]
        billing_items = [e for e in evidence if e.source_type == "billing"]

        sentences = []
        citations = extract_citations_from_evidence(evidence)

        # Case 1: Coverage details present
        if cov_items:
            primary_cov = cov_items[0]
            sentences.append(f"Based on your policy schedule, {primary_cov.content}.")

        # Case 2: Matching clause with approved explanation
        if clause_items:
            primary_clause = clause_items[0]
            explanation = primary_clause.plain_language or primary_clause.content
            source_ref = f"Under {primary_clause.form_number}"
            if primary_clause.heading:
                source_ref += f" ({primary_clause.heading})"
            sentences.append(f"{source_ref}: {explanation}")

        # Case 3: Attached form inquiry
        elif form_items:
            primary_form = form_items[0]
            sentences.append(f"This policy attaches {primary_form.content}.")

        # Case 4: Claims inquiry
        elif claim_items:
            primary_claim = claim_items[0]
            sentences.append(f"Regarding claims on this policy: {primary_claim.content}.")

        # Case 5: Billing inquiry
        elif billing_items:
            primary_bill = billing_items[0]
            sentences.append(f"Regarding billing on this policy: {primary_bill.content}.")

        if not sentences:
            sentences.append(
                "The available policy documentation does not establish a specific answer to this question."
            )

        final_answer = " ".join(sentences)

        return LLMGenerationResult(
            answer=final_answer,
            raw_response=final_answer,
            citations=citations,
            confidence="high" if (cov_items or clause_items) else "medium",
            model_used="grounded-carrier-engine",
            is_fallback=True,
        )
