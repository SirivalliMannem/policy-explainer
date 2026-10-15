"""Explain one cited policy clause in plain words, on request.

The carrier's approved plain-language explanation is not stored for every clause. When an employee
asks, the language model rewrites the clause's own wording in plain English. The explanation is
grounded only in that clause: it may not add terms, amounts or conditions, and it never says whether
a particular loss is covered. It is shown labelled as an AI explanation, never as approved wording.

When no model is available (no key, rate limit, timeout) nothing is generated: the caller is told
the explanation is unavailable, so nothing is invented.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from app.services.llm.exceptions import LLMConfigurationError, LLMProviderError
from app.services.llm.llm_service import LLMService

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15.0
MAX_CLAUSE_CHARS = 4000
MAX_EXPLANATION_CHARS = 1200

SYSTEM_PROMPT = """You explain one clause of an insurance policy in plain English for an insurance employee.

Rules:
- Use only the clause text you are given. Do not add amounts, limits, conditions, exceptions or examples that the clause does not state.
- Keep every condition and exception the clause contains; do not soften or drop any of them.
- Do not say whether any particular loss or claim is covered or will be paid.
- Do not give advice or mention other parts of the policy.
- Write 2 to 4 short sentences in everyday words, addressed to nobody in particular ("This clause ...").
- Reply with the explanation only: no heading, no quotation of the clause, no preamble."""

# A coverage decision is never part of an explanation of wording.
DECISION = re.compile(
    r"\b(?:your|the)\s+(?:claim|loss)\s+(?:is|will\s+be|would\s+be)\s+(?:covered|paid|approved|denied)\b"
    r"|\bwe\s+will\s+(?:pay|approve|deny)\s+(?:your|this)\b",
    re.IGNORECASE,
)


@dataclass
class PlainLanguageResult:
    status: str  # explained | unavailable
    explanation: str = ""
    model_used: Optional[str] = None
    provider: Optional[str] = None
    reason: Optional[str] = None


def explain_clause(heading: str, form_number: str, text: str) -> PlainLanguageResult:
    clause = (text or "").strip()[:MAX_CLAUSE_CHARS]
    if not clause:
        return PlainLanguageResult("unavailable", reason="The clause has no text to explain.")
    try:
        provider = LLMService.get_provider()
        if not provider.is_configured:
            raise LLMConfigurationError(f"No API key configured for provider '{provider.name}'")
        user = f"Form: {form_number or 'not stated'}\nHeading: {heading or 'not stated'}\nClause:\n{clause}"
        raw = provider.complete(
            SYSTEM_PROMPT, user, max_tokens=400, timeout_seconds=TIMEOUT_SECONDS, retry_rate_limit=False
        )
    except (LLMConfigurationError, LLMProviderError) as exc:
        logger.warning("Plain-language explanation unavailable: %s", type(exc).__name__)
        return PlainLanguageResult(
            "unavailable",
            reason="The language model is not available right now (it may be busy). Try again in a moment.",
        )
    explanation = " ".join((raw or "").split())[:MAX_EXPLANATION_CHARS].strip()
    if not explanation:
        return PlainLanguageResult("unavailable", reason="The language model returned no explanation. Try again.")
    if DECISION.search(explanation):
        logger.warning("Plain-language explanation withheld: it stated a coverage decision")
        return PlainLanguageResult(
            "unavailable",
            reason="The explanation was withheld because it went beyond the wording (it stated a coverage decision).",
        )
    return PlainLanguageResult("explained", explanation, model_used=provider.model, provider=provider.name)
