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
    ) -> AIServiceResponse:
        """Send question and policy context to AI Service and return structured explanation."""
        payload = {
            "question": question,
            "policy_id": policy_id,
            "conversation_id": conversation_id,
            "policy_context": policy_context.model_dump() if policy_context else None,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                url = f"{self.base_url}/api/explain"
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    return AIServiceResponse.model_validate(resp.json())
                elif resp.status_code == 404:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=resp.json().get("detail", "Policy not found in AI service"),
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"AI service returned status {resp.status_code}: {resp.text}",
                    )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Failed to communicate with AI Service: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to communicate with AI service: {str(exc)}",
            )


# Global singleton client instance
ai_client = AIServiceClient()
