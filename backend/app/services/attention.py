"""Questions that need a person: flagged or unanswered entries in the evidence ledger.

Everything here is derived from recorded answers and their stored analysis (attention_analysis,
written once when the answer was flagged). An item is closed by asking a verified suggestion or an
edited question as a new question, or by dismissing it with a reason. The closure is recorded in
attention_resolution and covers every repeat of the question up to the one closed; the flagged
ledger entries themselves are never changed. A re-asked question that is flagged again appears as a
new item marked as a re-run of the original; the original is never reopened.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.attention import AttentionResolution
from app.models.ledger import EvidenceLedger
from app.models.policy import CoreAccount, CorePolicy
from app.schemas.dashboard import (
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

# How an item was closed. The first four are the current actions; the rest label closures recorded
# before suggestion-based resolving, which stay in the log as they were.
ACTION_LABELS = {
    "asked_suggestion": "Asked a suggestion",
    "edited_and_asked": "Edited and asked",
    "added_edition": "Added the missing edition",
    "dismissed": "Dismissed as out of scope",
    "confirmed_not_covered": "Confirmed not covered by the policy wording",
    "referred_underwriting": "Referred to underwriting",
    "reasked": "Asked again",
    "approved_after_review": "Approved after review",
    "rejected_escalated": "Rejected and escalated",
    "confirmed_not_on_file": "Confirmed customer not on file",
    "confirmed_correct": "Confirmed answer is correct",
    "escalated_specialist": "Escalated to a specialist",
}
ASK_ACTIONS = ("asked_suggestion", "edited_and_asked")


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
        if retrieval.get("answer_type") in ("portfolio", "customer_verification_failed"):
            return "customer_not_found"
        cust_v = retrieval.get("customer_verification")
        if isinstance(cust_v, dict) and cust_v.get("status") in ("not_found", "customer_not_found"):
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


def _closed_until(db: Session) -> dict[tuple[str, str], datetime]:
    """For each question, the time of the latest repeat a closure covers: repeats asked up to then
    are closed; anything asked later (a re-run, or the question asked again) is a new item."""
    rows = (
        db.query(AttentionResolution, EvidenceLedger.created_at)
        .outerjoin(EvidenceLedger, EvidenceLedger.id == AttentionResolution.latest_entry_id)
        .all()
    )
    until: dict[tuple[str, str], datetime] = {}
    for resolution, closed_entry_at in rows:
        key = (resolution.question_key, resolution.policy_id or "")
        cutoff = closed_entry_at or resolution.resolved_at
        if key not in until or cutoff > until[key]:
            until[key] = cutoff
    return until


def needs_attention(db: Session, since: datetime, range_name: str, limit: int = 50) -> AttentionResponse:
    rows = (
        db.query(EvidenceLedger, CorePolicy, CoreAccount)
        .outerjoin(CorePolicy, CorePolicy.id == EvidenceLedger.policy_id)
        .outerjoin(CoreAccount, CoreAccount.id == CorePolicy.account_id)
        .filter(EvidenceLedger.created_at >= since)
        .order_by(EvidenceLedger.created_at.asc())
        .all()
    )

    closed_until = _closed_until(db)
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
        if key in closed_until and entry.created_at <= closed_until[key]:
            resolved_groups.add(key)  # covered by a closure: not in the queue
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
        if entry.attention_analysis:
            group["analysis"] = (entry.id, entry.attention_analysis)

    items = []
    for group in groups.values():
        entry, policy, account, reason = group["item"]
        retrieval = entry.retrieval or {}
        analysed = group.get("analysis")
        items.append(
            AttentionItem(
                question=entry.question.strip(),
                reason=reason,
                reason_label=REASONS[reason][0],
                detail=_detail(entry, reason),
                policy_number=policy.policy_number if policy else None,
                policy_id=entry.policy_id or (policy.id if policy else None),
                conversation_id=entry.conversation_id,
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
                # Stored when the answer was flagged; read only, never computed on load.
                analysis=analysed[1] if analysed else None,
                analysis_entry_id=analysed[0] if analysed else None,
                rerun_of=retrieval.get("rerun_of"),
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
    """The closure that covers this entry: the first one recorded for its question whose closed
    repeat was asked at or after this entry."""
    key, policy_id = _group_key(entry)
    query = (
        db.query(AttentionResolution)
        .outerjoin(EvidenceLedger, EvidenceLedger.id == AttentionResolution.latest_entry_id)
        .filter(AttentionResolution.question_key == key, EvidenceLedger.created_at >= entry.created_at)
    )
    if policy_id:
        query = query.filter(AttentionResolution.policy_id == policy_id)
    else:
        query = query.filter(AttentionResolution.policy_id.is_(None))
    return query.order_by(AttentionResolution.resolved_at.asc()).first()


def record_closure(
    entry: EvidenceLedger,
    action: str,
    employee,
    db: Session,
    note: str = "",
    new_question: Optional[str] = None,
    new_entry_id: Optional[str] = None,
) -> AttentionResolution:
    """Close a flagged item (and every earlier repeat of it). The ledger entry is not modified."""
    row = AttentionResolution(
        question_key=question_key(entry.question),
        policy_id=entry.policy_id,
        question=entry.question.strip(),
        reason=_reason(entry) or "",
        action=action,
        note=(note or "").strip(),
        new_question=new_question,
        new_entry_id=new_entry_id,
        latest_entry_id=entry.id,
        resolved_by=employee.id,
        resolved_by_name=employee.name if getattr(employee, "identified", False) else None,
        resolved_by_role=employee.role,
        resolved_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def latest_in_group(entry: EvidenceLedger, db: Session) -> EvidenceLedger:
    """The most recent flagged repeat of the entry's question, so a closure covers all repeats."""
    key, policy_id = _group_key(entry)
    query = db.query(EvidenceLedger).filter(EvidenceLedger.created_at >= entry.created_at)
    query = query.filter(EvidenceLedger.policy_id == policy_id) if policy_id else query.filter(EvidenceLedger.policy_id.is_(None))
    latest = entry
    for candidate in query.order_by(EvidenceLedger.created_at.asc()).all():
        if _group_key(candidate) == (key, policy_id) and _reason(candidate) is not None:
            latest = candidate
    return latest


def resolution_log(db: Session, since: datetime, limit: int = 50) -> list[AttentionResolutionSchema]:
    rows = (
        db.query(AttentionResolution)
        .filter(AttentionResolution.resolved_at >= since)
        .order_by(AttentionResolution.resolved_at.desc())
        .limit(limit)
        .all()
    )
    return [resolution_payload(r) for r in rows]


def resolution_payload(row: AttentionResolution) -> AttentionResolutionSchema:
    return AttentionResolutionSchema(
        id=row.id,
        question=row.question,
        reason=row.reason,
        action=row.action,
        action_label=ACTION_LABELS.get(row.action, row.action.replace("_", " ")),
        note=row.note or "",
        latest_entry_id=row.latest_entry_id,
        new_question=row.new_question,
        new_entry_id=row.new_entry_id,
        resolved_by=row.resolved_by,
        resolved_by_name=row.resolved_by_name,
        resolved_by_role=row.resolved_by_role,
        resolved_at=row.resolved_at,
    )
