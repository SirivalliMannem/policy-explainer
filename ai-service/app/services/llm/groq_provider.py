"""Groq LLM provider implementation using OpenAI-compatible chat completions API."""
from __future__ import annotations

import logging
from typing import Optional
import httpx

from app.services.llm.base import (
    BaseLLMProvider,
    LLMGenerationResult,
    SYSTEM_PROMPT,
    extract_citations_from_evidence,
)
from app.services.llm.exceptions import LLMProviderError
from app.services.retrieval.evidence_retriever import EvidenceItem

logger = logging.getLogger(__name__)


class GroqProvider(BaseLLMProvider):
    """Provider for Groq Cloud API."""

    name: str = "groq"
    key_env_var: str = "GROQ_API_KEY"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model or "openai/gpt-oss-120b",
            base_url=base_url or "https://api.groq.com/openai/v1",
            timeout_seconds=timeout_seconds,
        )

    def generate(
        self,
        question: str,
        grounding_context: str,
        evidence: list[EvidenceItem],
    ) -> Optional[LLMGenerationResult]:
        """Invoke Groq chat completions endpoint with grounded prompt."""
        self.validate_configuration()

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        user_content = (
            f"{grounding_context}\n\n"
            f"Based ONLY on the above evidence, answer the employee question: '{question}'."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
            "max_tokens": 600,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        message = choices[0].get("message", {})
                        content = message.get("content", "").strip()
                        if content:
                            citations = extract_citations_from_evidence(evidence)
                            return LLMGenerationResult(
                                answer=content,
                                raw_response=content,
                                citations=citations,
                                confidence="high",
                                model_used=self.model,
                                is_fallback=False,
                            )
                else:
                    # Log failure without leaking auth credentials
                    logger.warning(
                        "Groq API returned HTTP %s (model=%s)",
                        resp.status_code,
                        self.model,
                    )
                    raise LLMProviderError(f"Groq API error: HTTP {resp.status_code}")
        except httpx.RequestError as exc:
            logger.warning("Groq network request failed: %s", type(exc).__name__)
            raise LLMProviderError(f"Groq network error: {type(exc).__name__}") from exc

        return None
