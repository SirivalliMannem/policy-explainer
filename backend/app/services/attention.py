"""Questions that need a person: flagged or unanswered entries in the evidence ledger.

Everything here is derived from recorded answers. A person resolves a flagged question by choosing
one of the actions offered for its flag reason; the resolution is recorded in attention_resolution
and the ledger entries are never changed. A resolved question leaves the queue until it is asked
again.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.attention import AttentionResolution
from app.models.ledger import EvidenceLedger
from app.models.policy import CoreAccount, CorePolicy
from app.schemas.dashboard import (
    AttentionAction,
    AttentionResolution as AttentionResolutionSchema,
    AttentionCause,
    AttentionItem,
    AttentionResponse,
    AttentionSources,
)
from app.services.ledger.ledger_service import answer_outcome

# reason -> (label, description); order is the display order of the causes.
REASONS: dict[str, tuple[str, str]] = {
    "guardrail_flagged": ("Guardrail flagged", "An answer was written but a safety check blocked it"),
    "no_evidence": ("No matching evidence", "Nothing in the policy or its forms matched"),
    "customer_not_found": ("Customer not found", "The named policyholder is not on file"),
    "low_confidence": ("Low confidence", "Answered, but on weak evidence"),
}

_PUNCT = re.compile(r"[^\w\s-]")

# reason -> the actions that resolve it: (key, label, description, kind).
ACTIONS: dict[str, list[tuple[str, str, str, str]]] = {
    "no_evidence": [
        ("confirmed_not_covered", "Confirm not covered by the policy wording",
         "The forms do not address this. Record that, so the customer can be told the policy is silent on it.", "resolve"),
        ("referred_underwriting", "Refer to underwriting",
         "Hand the question to underwriting to decide whether cover exists.", "resolve"),
        ("reasked", "Ask again with a clearer question",
         "Open the chat with this question to rephrase it in policy terms. Resolved once the new answer is grounded.", "reask"),
    ],
    "guardrail_flagged": [
        ("approved_after_review", "Approve answer after review",
         "You checked the answer against the cited wording and it is correct.", "resolve"),
        ("rejected_escalated", "Reject answer and escalate",
         "The answer must not be relied on; a specialist will answer the customer.", "resolve"),
    ],
    "customer_not_found": [
        ("confirmed_not_on_file", "Confirm customer not on file",
         "The person asked about has no policy with us.", "resolve"),
        ("reasked", "Ask again with the policy number",
         "Open the chat and ask with the policy number. Resolved once the new answer is grounded.", "reask"),
    ],
    "low_confidence": [
        ("confirmed_correct", "Confirm answer is correct",
         "You checked the answer against the cited wording and it holds.", "resolve"),
        ("escalated_specialist", "Escalate to a specialist",
         "The evidence is too weak to rely on; a specialist will review it.", "resolve"),
    ],
}

ACTION_LABELS = {key: label for actions in ACTIONS.values() for key, label, _, _ in actions}


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


def question_key(question: str) -> str:
    """The question's wording, normalised the way the queue groups it."""
    return " ".join(_PUNCT.sub("", (question or "").lower()).split())[:500]


def _group_key(entry: EvidenceLedger) -> tuple[str, str]:
    return question_key(entry.question), entry.policy_id or ""


def _suggestion(entry: EvidenceLedger, reason: str, policy_number: Optional[str]) -> str:
    """A next step written from what the record shows; nothing is inferred beyond it."""
    retrieval = entry.retrieval or {}
    if reason == "no_evidence":
        terms = list(retrieval.get("query_terms") or [])[:5]
        searched = (retrieval.get("clauses_searched") or 0) + (retrieval.get("coverages_searched") or 0)
        where = f" on {policy_number}" if policy_number else ""
        found = "None of " + ", ".join(f"\u201c{t}\u201d" for t in terms) + " matched" if terms else "Nothing matched"
        return (
            f"{found} in the {searched} clauses and coverages searched{where}. If the customer means something the "
            "policy names (a peril, a coverage, a form), ask again in those terms; if not, confirm that the policy "
            "wording does not address it."
        )
    if reason == "guardrail_flagged":
        failed = [c.get("name", "").replace("_", " ") for c in (entry.guardrail_checks or [])
                  if isinstance(c, dict) and c.get("status") == "failed"]
        checks = ", ".join(f for f in failed if f) or "a safety check"
        return (
            f"The answer failed {checks}. Read it against its cited sources (Open record): approve it if it is "
            "correct, otherwise reject it so a specialist answers the customer."
        )
    if reason == "customer_not_found":
        return "The policyholder named in the question is not on file. Check the spelling, or ask again with the policy number."
    return (
        "The answer was given on weak evidence. Check it against the cited wording (Open record) and confirm it, "
        "or escalate it to a specialist."
    )


def _latest_resolutions(db: Session) -> dict[tuple[str, str], AttentionResolution]:
    latest: dict[tuple[str, str], AttentionResolution] = {}
    for row in db.query(AttentionResolution).order_by(AttentionResolution.resolved_at.asc()).all():
        latest[(row.question_key, row.policy_id or "")] = row
    return latest


def needs_attention(db: Session, since: datetime, range_name: str, limit: int = 50) -> AttentionResponse:
    rows = (
        db.query(EvidenceLedger, CorePolicy, CoreAccount)
        .outerjoin(CorePolicy, CorePolicy.id == EvidenceLedger.policy_id)
        .outerjoin(CoreAccount, CoreAccount.id == CorePolicy.account_id)
        .filter(EvidenceLedger.created_at >= since)
        .order_by(EvidenceLedger.created_at.asc())
        .all()
    )

    resolutions = _latest_resolutions(db)
    groups: dict[tuple[str, str], dict] = {}
    cause_counts: Counter = Counter()
    unmatched_terms: Counter = Counter()
    examples: dict[str, Counter] = {r: Counter() for r in REASONS}

    resolved_groups: set[tuple[str, str]] = set()
    for entry, policy, account in rows:
        reason = _reason(entry)
        if reason is None:
            continue
        key = _group_key(entry)
        resolution = resolutions.get(key)
        if resolution is not None and resolution.resolved_at >= entry.created_at:
            resolved_groups.add(key)  # resolved after this was asked: not in the queue
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
                suggestion=_suggestion(entry, reason, policy.policy_number if policy else None),
                actions=[AttentionAction(key=k, label=label, description=d, kind=kind) for k, label, d, kind in ACTIONS[reason]],
            )
        )
    # Newest first: the most recently asked question leads the list.
    items.sort(key=lambda i: i.last_asked_at, reverse=True)

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
        questions_resolved=len(resolved_groups - set(groups)),
        items=items[:limit],
        causes=causes,
    )


def flag_reason(entry: EvidenceLedger) -> Optional[str]:
    """Why a ledger entry is in the queue, or None when it is not flagged."""
    return _reason(entry)


def resolution_for_entry(entry: EvidenceLedger, db: Session) -> Optional[AttentionResolution]:
    """The first resolution recorded for this entry's question after it was asked."""
    key, policy_id = _group_key(entry)
    query = db.query(AttentionResolution).filter(
        AttentionResolution.question_key == key,
        AttentionResolution.resolved_at >= entry.created_at,
    )
    if policy_id:
        query = query.filter(AttentionResolution.policy_id == policy_id)
    else:
        query = query.filter(AttentionResolution.policy_id.is_(None))
    return query.order_by(AttentionResolution.resolved_at.asc()).first()


def resolution_payload(row: AttentionResolution) -> AttentionResolutionSchema:
    return AttentionResolutionSchema(
        id=row.id,
        question=row.question,
        reason=row.reason,
        action=row.action,
        action_label=ACTION_LABELS.get(row.action, row.action.replace("_", " ")),
        note=row.note or "",
        latest_entry_id=row.latest_entry_id,
        resolved_by=row.resolved_by,
        resolved_by_name=row.resolved_by_name,
        resolved_by_role=row.resolved_by_role,
        resolved_at=row.resolved_at,
    )
