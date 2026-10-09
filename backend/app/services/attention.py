"""Questions that need a person: flagged or unanswered entries in the evidence ledger.

Everything here is derived from recorded answers. There is no review workflow yet, so an
entry stays on the list for as long as it falls inside the selected time window.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.ledger import EvidenceLedger
from app.models.policy import CoreAccount, CorePolicy
from app.schemas.dashboard import AttentionCause, AttentionItem, AttentionResponse, AttentionSources
from app.services.ledger.ledger_service import answer_outcome

# reason -> (label, description); order is the display order of the causes.
REASONS: dict[str, tuple[str, str]] = {
    "guardrail_flagged": ("Guardrail flagged", "An answer was written but a safety check blocked it"),
    "no_evidence": ("No matching evidence", "Nothing in the policy or its forms matched"),
    "customer_not_found": ("Customer not found", "The named policyholder is not on file"),
    "low_confidence": ("Low confidence", "Answered, but on weak evidence"),
}

_PUNCT = re.compile(r"[^\w\s-]")


def _outcome(entry: EvidenceLedger) -> str:
    if entry.outcome:
        return entry.outcome
    question_status = "insufficient_evidence" if entry.confidence == "none" else "answered"
    return answer_outcome(question_status, entry.guardrail_status)


def _reason(entry: EvidenceLedger) -> Optional[str]:
    outcome = _outcome(entry)
    retrieval = entry.retrieval or {}
    if outcome == "needs_review":
        return "guardrail_flagged"
    if outcome == "insufficient_evidence":
        if retrieval.get("answer_type") == "portfolio":
            return "customer_not_found"
        return "no_evidence"
    if entry.confidence == "low":
        return "low_confidence"
    return None


def _detail(entry: EvidenceLedger, reason: str) -> str:
    failed = [c for c in (entry.guardrail_checks or []) if isinstance(c, dict) and c.get("status") == "failed"]
    if reason == "guardrail_flagged" and failed:
        return " ".join(c.get("detail") or c.get("name", "") for c in failed)
    if reason == "customer_not_found":
        return entry.final_answer
    if failed and failed[0].get("detail"):
        return failed[0]["detail"]
    return REASONS[reason][1] + "."


def _citation_label(c: dict) -> str:
    parts = [c.get("form_number") or ""]
    if c.get("page"):
        parts.append(f"p.{c['page']}")
    if c.get("heading"):
        parts.append(c["heading"])
    return " · ".join(p for p in parts if p)


def _group_key(entry: EvidenceLedger) -> tuple[str, str]:
    text = " ".join(_PUNCT.sub("", entry.question.lower()).split())
    return text, entry.policy_id or ""


def needs_attention(db: Session, since: datetime, range_name: str, limit: int = 50) -> AttentionResponse:
    rows = (
        db.query(EvidenceLedger, CorePolicy, CoreAccount)
        .outerjoin(CorePolicy, CorePolicy.id == EvidenceLedger.policy_id)
        .outerjoin(CoreAccount, CoreAccount.id == CorePolicy.account_id)
        .filter(EvidenceLedger.created_at >= since)
        .order_by(EvidenceLedger.created_at.asc())
        .all()
    )

    groups: dict[tuple[str, str], dict] = {}
    cause_counts: Counter = Counter()
    unmatched_terms: Counter = Counter()
    examples: dict[str, Counter] = {r: Counter() for r in REASONS}

    for entry, policy, account in rows:
        reason = _reason(entry)
        if reason is None:
            continue
        cause_counts[reason] += 1
        retrieval = entry.retrieval or {}
        if reason == "no_evidence":
            unmatched_terms.update(retrieval.get("query_terms") or [])
        elif reason == "guardrail_flagged":
            examples[reason].update(
                c.get("name", "") for c in (entry.guardrail_checks or []) if isinstance(c, dict) and c.get("status") == "failed"
            )
        else:
            examples[reason][entry.question.strip()] += 1

        key = _group_key(entry)
        group = groups.get(key)
        if group is None:
            group = groups[key] = {"first": entry.created_at, "count": 0}
        group["count"] += 1
        group["last"] = entry.created_at
        # Rows are oldest first, so the latest occurrence wins for display.
        group["item"] = (entry, policy, account, reason)

    items = []
    for group in groups.values():
        entry, policy, account, reason = group["item"]
        retrieval = entry.retrieval or {}
        items.append(
            AttentionItem(
                question=entry.question.strip(),
                reason=reason,
                reason_label=REASONS[reason][0],
                detail=_detail(entry, reason),
                policy_number=policy.policy_number if policy else None,
                insured=account.name if account else None,
                line_of_business=policy.line_of_business if policy else None,
                times_asked=group["count"],
                first_asked_at=group["first"],
                last_asked_at=group["last"],
                latest_entry_id=entry.id,
                sources=AttentionSources(
                    query_terms=list(retrieval.get("query_terms") or [])[:8],
                    coverages_searched=retrieval.get("coverages_searched") or 0,
                    forms_searched=retrieval.get("forms_searched") or 0,
                    clauses_searched=retrieval.get("clauses_searched") or 0,
                    citations=[_citation_label(c) for c in (entry.citations or []) if isinstance(c, dict)][:4],
                ),
            )
        )
    # Longest-waiting first, as a review queue reads.
    items.sort(key=lambda i: i.first_asked_at)

    flagged = sum(cause_counts.values())
    examples["no_evidence"] = unmatched_terms
    causes = [
        AttentionCause(
            reason=reason,
            label=label,
            description=description,
            count=cause_counts[reason],
            share_pct=round(cause_counts[reason] / flagged * 100, 1) if flagged else 0.0,
            examples=[text for text, _ in examples[reason].most_common(4) if text],
        )
        for reason, (label, description) in REASONS.items()
        if cause_counts[reason]
    ]
    causes.sort(key=lambda c: -c.count)

    return AttentionResponse(
        range=range_name,
        answers_total=len(rows),
        flagged_total=flagged,
        questions_flagged=len(items),
        items=items[:limit],
        causes=causes,
    )
