"""Google Gemini LLM provider implementation using generateContent REST endpoint."""
from __future__ import annotations

import logging
from typing import Optional
import httpx

from app.services.llm.base import (
    BaseLLMProvider,
    LLMGenerationResult,
    SYSTEM_PROMPT,
    USER_INSTRUCTION,
    extract_citations_from_evidence,
)
from app.services.llm.exceptions import LLMProviderError
from app.services.retrieval.evidence_retriever import EvidenceItem

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Provider for Google Gemini API."""

    name: str = "gemini"
    key_env_var: str = "GEMINI_API_KEY"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model or "gemini-2.5-flash",
            base_url=base_url or "https://generativelanguage.googleapis.com/v1beta",
            timeout_seconds=timeout_seconds,
        )

    def generate(
        self,
        question: str,
        grounding_context: str,
        evidence: list[EvidenceItem],
    ) -> Optional[LLMGenerationResult]:
        """Invoke Gemini generateContent endpoint with grounded prompt."""
        self.validate_configuration()

        # Endpoint uses query parameter key - never log the full URL
        url = f"{self.base_url.rstrip('/')}/models/{self.model}:generateContent?key={self.api_key}"
        headers = {
            "Content-Type": "application/json",
        }

        user_content = f"{grounding_context}\n\n{USER_INSTRUCTION.format(question=question)}"

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{user_content}"}],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 600,
            },
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            content = parts[0]["text"].strip()
                            if content:
                                citations = extract_citations_from_evidence(evidence)
                                return LLMGenerationResult(
                                    answer=content,
                                    raw_response=content,
                                    citations=citations,
                                    confidence="high",
                                    model_used=self.model,
                                    is_fallback=False,
                                    provider=self.name,
                                )
                    raise LLMProviderError("Gemini returned an empty answer")
                else:
                    # Log failure without leaking the API key in the URL
                    logger.warning(
                        "Gemini API returned HTTP %s (model=%s)",
                        resp.status_code,
                        self.model,
                    )
                    raise LLMProviderError(f"Gemini API error: HTTP {resp.status_code}")
        except httpx.RequestError as exc:
            logger.warning("Gemini network request failed: %s", type(exc).__name__)
            raise LLMProviderError(f"Gemini network error: {type(exc).__name__}") from exc

        return None
