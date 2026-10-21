"""HTTP client the backend uses to call an agent service."""

from __future__ import annotations

import logging
from typing import Optional
import httpx
from fastapi import HTTPException, status

from fi360_shared.agents import POLICY_EXPLAINER

from app.schemas.conversation import PolicyContextSummary
from app.schemas.explainer import AIServiceResponse
from app.services.agent_registry import agent_base_url

logger = logging.getLogger(__name__)

# Upper bound for one explain call: retrieval + an LLM call (provider timeout 20s) + validation.
AI_SERVICE_TIMEOUT_SECONDS = 45.0
# Interpretation is one short model call (8s provider timeout, no rate-limit retry) with a rules fallback.
INTERPRET_TIMEOUT_SECONDS = 15.0
# A plain-language explanation is one short model call (15s provider timeout, no rate-limit retry).
PLAIN_LANGUAGE_TIMEOUT_SECONDS = 25.0
# Attention analysis: one model call (15s) plus a retrieval for each of at most two candidates.
ATTENTION_ANALYSIS_TIMEOUT_SECONDS = 45.0


class AIServiceClient:
    """Client for calling one agent service. Defaults to Policy Explainer (A02)."""

    def __init__(self, base_url: Optional[str] = None, agent_code: str = POLICY_EXPLAINER):
        self.agent_code = agent_code
        self.base_url = (base_url or agent_base_url(agent_code)).rstrip("/")

    def explain(
        self,
        question: str,
        policy_id: str,
        conversation_id: Optional[str] = None,
        policy_context: Optional[PolicyContextSummary] = None,
        previous_question: Optional[str] = None,
        interpretation: Optional[dict] = None,
    ) -> AIServiceResponse:
        """Send question and policy context to AI Service and return structured explanation."""
        payload = {
            "question": question,
            "policy_id": policy_id,
            "conversation_id": conversation_id,
            "policy_context": policy_context.model_dump() if policy_context else None,
            "previous_question": previous_question,
            "interpretation": interpretation,
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

    def interpret(self, question: str, previous_question: Optional[str] = None) -> Optional[dict]:
        """Ask the AI service how a question should be understood.

        Never raises: when the AI service cannot be reached, callers continue with the raw question
        exactly as before, and the failure surfaces at answer time.
        """
        try:
            with httpx.Client(timeout=INTERPRET_TIMEOUT_SECONDS) as client:
                resp = client.post(
                    f"{self.base_url}/api/explain/interpret",
                    json={"question": question, "previous_question": previous_question},
                )
            if resp.status_code == 200:
                return resp.json()
            logger.warning("AI service interpret returned HTTP %s", resp.status_code)
        except httpx.HTTPError as exc:
            logger.warning("AI service interpret unavailable: %s", type(exc).__name__)
        return None

    def plain_language(self, heading: str, form_number: str, text: str) -> dict:
        """Ask the AI service to explain one clause in plain words.

        Never raises: when the AI service cannot be reached the result says the explanation is
        unavailable, so nothing is invented.
        """
        try:
            with httpx.Client(timeout=PLAIN_LANGUAGE_TIMEOUT_SECONDS) as client:
                resp = client.post(
                    f"{self.base_url}/api/explain/plain-language",
                    json={"heading": heading, "form_number": form_number, "text": text},
                )
            if resp.status_code == 200:
                return resp.json()
            logger.warning("AI service plain-language returned HTTP %s", resp.status_code)
        except httpx.HTTPError as exc:
            logger.warning("AI service plain-language unavailable: %s", type(exc).__name__)
        return {"status": "unavailable", "reason": "The AI service is not reachable right now. Try again in a moment."}

    def attention_analysis(self, question: str, policy_id: Optional[str], retrieval: dict, flag_reason: str) -> Optional[dict]:
        """Analyse a flagged question (classification + verified alternatives). None when unreachable."""
        try:
            with httpx.Client(timeout=ATTENTION_ANALYSIS_TIMEOUT_SECONDS) as client:
                resp = client.post(
                    f"{self.base_url}/api/explain/attention-analysis",
                    json={"question": question, "policy_id": policy_id, "retrieval": retrieval, "flag_reason": flag_reason},
                )
            if resp.status_code == 200:
                return resp.json()
            logger.warning("AI service attention-analysis returned HTTP %s", resp.status_code)
        except httpx.HTTPError as exc:
            logger.warning("AI service attention-analysis unavailable: %s", type(exc).__name__)
        return None

    def explain_document(
        self, document_id: str, question: str, mode: str = "question", policy_id: Optional[str] = None
    ) -> AIServiceResponse:
        """Answer about one uploaded document (mode "summary": explain the whole document). With the
        conversation's policy, its relevant wording is given too, for comparison."""
        payload = {"document_id": document_id, "question": question, "mode": mode, "policy_id": policy_id}
        try:
            with httpx.Client(timeout=AI_SERVICE_TIMEOUT_SECONDS) as client:
                resp = client.post(f"{self.base_url}/api/explain/document", json=payload)
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"AI service did not respond within {int(AI_SERVICE_TIMEOUT_SECONDS)} seconds.",
            )
        except httpx.RequestError as exc:
            logger.error("AI service unreachable at %s: %s", self.base_url, type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service is unavailable. The document question could not be answered.",
            )
        if resp.status_code == 200:
            return AIServiceResponse.model_validate(resp.json())
        logger.error("AI service document answer returned HTTP %s", resp.status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service could not answer from the document.",
        )


# Global singleton client instance
ai_client = AIServiceClient()
