"""Confidence as a percentage for a recorded answer.

The same rule as the chat's confidence badge (frontend/src/lib/confidence.ts), which is derived from
the rule the AI service uses for its HIGH / MEDIUM / LOW label (_grade_confidence in
ai-service explainer_pipeline.py). Nothing here is a new score: the percentage is the share of that
rule's criteria the answer meets.
"""

from __future__ import annotations

from typing import Any, Optional

# STRONG_EVIDENCE_SCORE in ai-service/app/services/explainer_pipeline.py.
STRONG_EVIDENCE_SCORE = 12

# No answer is shown as certain (100%) or as having no support at all (0%); same bounds as
# MIN/MAX_CONFIDENCE_PERCENT in frontend/src/lib/confidence.ts.
MIN_PERCENT = 5
MAX_PERCENT = 98


def _get(item: Any, key: str):
    return item.get(key) if isinstance(item, dict) else getattr(item, key, None)


def confidence_percent(
    confidence: str,
    answer_type: Optional[str],
    evidence: list,
    citations: list,
    guardrail_checks: list,
    guardrail_status: str,
) -> Optional[int]:
    """The share of confidence criteria met, or None where there is no percentage to give.

    None for portfolio answers, withheld answers (confidence "none") and older answers recorded
    without guardrail checks.
    """
    if answer_type == "portfolio" or (confidence or "").lower() == "none":
        return None
    evidence = evidence or []
    verified = len(citations or [])
    if answer_type == "factual_lookup":
        criteria = [
            len(evidence) > 0,
            guardrail_status == "passed",
            len(evidence) > 0 and verified >= len(evidence),
        ]
    else:
        if not guardrail_checks:
            return None
        searched = [e for e in evidence if _get(e, "scope") != "policy_record"]
        top = max((_get(e, "relevance_score") or 0 for e in searched), default=0)
        inline = next((c for c in guardrail_checks if _get(c, "name") == "inline_citations"), None)
        criteria = [
            len(evidence) > 0,
            guardrail_status == "passed",
            verified >= 1,
            verified >= 2,
            inline is not None and _get(inline, "status") == "passed",
            top >= STRONG_EVIDENCE_SCORE,
        ]
    return min(MAX_PERCENT, max(MIN_PERCENT, round(sum(criteria) / len(criteria) * 100)))
