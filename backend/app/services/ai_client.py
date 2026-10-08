"""HTTP client for Backend to AI Service microservice communication."""

from __future__ import annotations

import logging
from typing import Optional
import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.conversation import PolicyContextSummary
from app.schemas.explainer import AIServiceResponse

logger = logging.getLogger(__name__)

# Upper bound for one explain call: retrieval + an LLM call (provider timeout 20s) + validation.
AI_SERVICE_TIMEOUT_SECONDS = 45.0


class AIServiceClient:
    """Client for calling the AI microservice."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.AI_SERVICE_URL).rstrip("/")

    def explain(
        self,
        question: str,
        policy_id: str,
        conversation_id: Optional[str] = None,
        policy_context: Optional[PolicyContextSummary] = None,
        previous_question: Optional[str] = None,
    ) -> AIServiceResponse:
        """Send question and policy context to AI Service and return structured explanation."""
        payload = {
            "question": question,
            "policy_id": policy_id,
            "conversation_id": conversation_id,
            "policy_context": policy_context.model_dump() if policy_context else None,
            "previous_question": previous_question,
        }

        url = f"{self.base_url}/api/explain"
        try:
            with httpx.Client(timeout=AI_SERVICE_TIMEOUT_SECONDS) as client:
                resp = client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            logger.error("AI service timed out after %ss: %s", AI_SERVICE_TIMEOUT_SECONDS, type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"AI service did not respond within {int(AI_SERVICE_TIMEOUT_SECONDS)} seconds.",
            )
        except httpx.RequestError as exc:
            logger.error("AI service unreachable at %s: %s", self.base_url, type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service is unavailable. The question was recorded but could not be answered.",
            )

        if resp.status_code == 200:
            return AIServiceResponse.model_validate(resp.json())
        if resp.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=resp.json().get("detail", "Policy not found in AI service"),
            )
        logger.error("AI service returned HTTP %s", resp.status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service returned status {resp.status_code}: {resp.text[:300]}",
        )


# Global singleton client instance
ai_client = AIServiceClient()
