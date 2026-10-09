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
        user_content = f"{grounding_context}\n\n{USER_INSTRUCTION.format(question=question)}"
        content = self.complete(SYSTEM_PROMPT, user_content, max_tokens=600)
        return LLMGenerationResult(
            answer=content,
            raw_response=content,
            citations=extract_citations_from_evidence(evidence),
            confidence="high",
            model_used=self.model,
            is_fallback=False,
            provider=self.name,
        )

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 600,
        json_mode: bool = False,
        timeout_seconds: Optional[float] = None,
        retry_rate_limit: bool = True,  # Gemini calls are never retried; accepted for interface parity
    ) -> str:
        """Run one generateContent call and return the text. Raises LLMProviderError on failure."""
        self.validate_configuration()

        # Endpoint uses query parameter key - never log the full URL
        url = f"{self.base_url.rstrip('/')}/models/{self.model}:generateContent?key={self.api_key}"
        headers = {
            "Content-Type": "application/json",
        }
        generation_config = {"temperature": 0.1, "maxOutputTokens": max_tokens}
        if json_mode:
            generation_config["responseMimeType"] = "application/json"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": f"{system}\n\n{user}"}]}],
            "generationConfig": generation_config,
        }

        try:
            with httpx.Client(timeout=timeout_seconds or self.timeout_seconds) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    # Log failure without leaking the API key in the URL
                    logger.warning("Gemini API returned HTTP %s (model=%s)", resp.status_code, self.model)
                    raise LLMProviderError(f"Gemini API error: HTTP {resp.status_code}")
                candidates = resp.json().get("candidates", [])
                parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
                content = (parts[0].get("text") if parts else "") or ""
                content = content.strip()
                if not content:
                    raise LLMProviderError("Gemini returned an empty answer")
                return content
        except httpx.RequestError as exc:
            logger.warning("Gemini network request failed: %s", type(exc).__name__)
            raise LLMProviderError(f"Gemini network error: {type(exc).__name__}") from exc
