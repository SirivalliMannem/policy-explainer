"""Groq LLM provider implementation using OpenAI-compatible chat completions API."""
from __future__ import annotations

import logging
import time
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

# Keeps a retried call inside the backend's 45s budget for the whole explain request.
MAX_RATE_LIMIT_WAIT_SECONDS = 6.0


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
        user_content = f"{grounding_context}\n\n{USER_INSTRUCTION.format(question=question)}"
        content = self.complete(SYSTEM_PROMPT, user_content, max_tokens=1500)
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
        max_tokens: int = 1500,
        json_mode: bool = False,
        timeout_seconds: Optional[float] = None,
        retry_rate_limit: bool = True,
    ) -> str:
        """Run one chat completion and return the visible text. Raises LLMProviderError on failure.

        ``retry_rate_limit=False`` fails fast on HTTP 429 for callers that have their own fallback
        and must answer quickly (question understanding).
        """
        self.validate_configuration()

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
            # Reasoning models spend completion tokens on hidden reasoning before the answer,
            # so the budget must cover both or the visible content comes back empty.
            "max_tokens": max_tokens,
        }
        if "gpt-oss" in self.model:
            payload["reasoning_effort"] = "low"
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            with httpx.Client(timeout=timeout_seconds or self.timeout_seconds) as client:
                resp = client.post(url, headers=headers, json=payload)
                # A short rate-limit window is worth one wait; anything longer falls back.
                if resp.status_code == 429 and retry_rate_limit:
                    try:
                        wait = float(resp.headers.get("retry-after", ""))
                    except ValueError:
                        wait = None
                    if wait is not None and 0 <= wait <= MAX_RATE_LIMIT_WAIT_SECONDS:
                        logger.warning("Groq rate limited; retrying once after %.1fs", wait)
                        time.sleep(wait)
                        resp = client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    # Log failure without leaking auth credentials
                    logger.warning("Groq API returned HTTP %s (model=%s)", resp.status_code, self.model)
                    raise LLMProviderError(f"Groq API error: HTTP {resp.status_code}")
                choices = resp.json().get("choices", [])
                content = ((choices[0].get("message", {}).get("content") if choices else "") or "").strip()
                if not content:
                    raise LLMProviderError("Groq returned an empty answer")
                return content
        except httpx.RequestError as exc:
            logger.warning("Groq network request failed: %s", type(exc).__name__)
            raise LLMProviderError(f"Groq network error: {type(exc).__name__}") from exc
