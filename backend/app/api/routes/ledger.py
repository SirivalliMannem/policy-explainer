"""Evidence Ledger audit endpoints ("The Record").

Every row is a persisted EvidenceLedger entry joined to the policy and policyholder it was
answered against. Nothing here is computed from anything other than recorded answers.
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.conversation import Conversation
from app.models.ledger import EvidenceLedger
from app.models.policy import CoreAccount, CorePolicy
from app.schemas.ledger import (
    LedgerDetail,
    LedgerFilterOption,
    LedgerFilters,
    LedgerPage,
    LedgerRow,
    LedgerSummary,
)
from app.services.ledger.ledger_service import answer_outcome

router = APIRouter(prefix="/api/ledger", tags=["evidence-ledger"])

# Evidence scopes that come from the insured's own policy rather than generic product wording.
CARRIER_SCOPES = {"customer_form", "policy_record"}
OUTCOMES = ["answered", "needs_review", "insufficient_evidence"]
SORTS = {"newest", "oldest", "slowest", "fastest"}


def _outcome(entry: EvidenceLedger) -> str:
    if entry.outcome:
        return entry.outcome
    # Rows recorded before outcomes were stored: derive it the same way submission does.
    question_status = "insufficient_evidence" if entry.confidence == "none" else "answered"
    return answer_outcome(question_status, entry.guardrail_status)


def _source_labels(citations: list[dict]) -> list[str]:
    labels: list[str] = []
    for c in citations or []:
        form = c.get("form_number") or c.get("heading")
        if not form:
            continue
        label = f"{form} · p.{c['page']}" if c.get("page") else form
        if label not in labels:
            labels.append(label)
    return labels


def _cites_carrier_source(entry: EvidenceLedger) -> bool:
    scope_by_source = {e.get("source_id"): e.get("scope") for e in (entry.retrieved_evidence or [])}
    return any(scope_by_source.get(c.get("source_id")) in CARRIER_SCOPES for c in (entry.citations or []))


def _row(entry: EvidenceLedger, policy: Optional[CorePolicy], account: Optional[CoreAccount],
         conversation: Optional[Conversation]) -> dict:
    sources = _source_labels(entry.citations or [])
    portfolio = (entry.retrieval or {}).get("portfolio") if (entry.retrieval or {}).get("answer_type") == "portfolio" else None
    insured = account.name if account else None
    if portfolio is not None and not insured:
        insured = ", ".join(portfolio.get("customers") or []) or "All policyholders"
    return dict(
        id=entry.id,
        created_at=entry.created_at,
        conversation_id=entry.conversation_id,
        question_id=entry.question_id,
        agent=entry.employee_id or (conversation.employee_id if conversation else None),
        insured=insured,
        answer_type="portfolio" if portfolio is not None else "policy_explanation",
        customer_id=account.id if account else None,
        policy_id=entry.policy_id,
        policy_number=policy.policy_number if policy else None,
        policy_term=policy.term_number if policy else None,
        policy_effective=policy.effective_date if policy else None,
        policy_expiration=policy.expiration_date if policy else None,
        state=policy.state if policy else None,
        line_of_business=policy.line_of_business if policy else None,
        question=entry.question,
        sources=sources,
        source_count=len(entry.citations or []),
        model_used=entry.model_used,
        provider=entry.provider,
        is_fallback=entry.is_fallback,
        confidence=entry.confidence,
        guardrail_status=entry.guardrail_status,
        outcome=_outcome(entry),
        # No review workflow exists yet, so no reviewer is ever recorded.
        reviewer=None,
        latency_ms=entry.latency_ms,
    )


def _base_query(db: Session):
    return (
        db.query(EvidenceLedger, CorePolicy, CoreAccount, Conversation)
        .outerjoin(CorePolicy, CorePolicy.id == EvidenceLedger.policy_id)
        .outerjoin(CoreAccount, CoreAccount.id == CorePolicy.account_id)
        .outerjoin(Conversation, Conversation.id == EvidenceLedger.conversation_id)
    )


@router.get("/summary", response_model=LedgerSummary)
def ledger_summary(db: Session = Depends(get_db)):
    """Headline audit metrics across every recorded answer."""
    entries = db.query(EvidenceLedger).all()
    total = len(entries)
    outcomes = [_outcome(e) for e in entries]
    carrier = sum(1 for e in entries if _cites_carrier_source(e))
    resolved = outcomes.count("answered")
    waiting = outcomes.count("needs_review") + outcomes.count("insufficient_evidence")

    latencies = sorted(e.latency_ms for e in entries if e.latency_ms is not None)
    p95 = latencies[max(math.ceil(0.95 * len(latencies)) - 1, 0)] if latencies else None

    def pct(count: int) -> float:
        return round(count / total * 100, 1) if total else 0.0

    return LedgerSummary(
        answers_recorded=total,
        carrier_source_count=carrier,
        carrier_source_pct=pct(carrier),
        resolved_without_person_count=resolved,
        resolved_without_person_pct=pct(resolved),
        p95_response_ms=p95,
        waiting_on_person=waiting,
        model_answers=sum(1 for e in entries if e.is_fallback is False and (e.model_used or "none") != "none"),
        fallback_answers=sum(1 for e in entries if e.is_fallback),
    )


@router.get("/filters", response_model=LedgerFilters)
def ledger_filters(db: Session = Depends(get_db)):
    """Filter values that actually occur in the ledger."""
    rows = _base_query(db).all()
    insureds = {account.id: account.name for _, _, account, _ in rows if account}
    return LedgerFilters(
        insureds=[LedgerFilterOption(value=k, label=v) for k, v in sorted(insureds.items(), key=lambda kv: kv[1])],
        states=sorted({p.state for _, p, _, _ in rows if p and p.state}),
        lines=sorted({p.line_of_business for _, p, _, _ in rows if p and p.line_of_business}),
        outcomes=OUTCOMES,
    )


@router.get("", response_model=LedgerPage)
def list_ledger(
    search: Optional[str] = Query(None, description="Matches question, answer, policy number or insured"),
    insured: Optional[str] = Query(None, description="Customer (account) id"),
    state: Optional[str] = Query(None),
    line: Optional[str] = Query(None, description="Line of business"),
    outcome: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    sort: str = Query("newest"),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List recorded answers with filters, newest first by default."""
    query = _base_query(db)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                EvidenceLedger.question.ilike(term),
                EvidenceLedger.final_answer.ilike(term),
                CorePolicy.policy_number.ilike(term),
                CoreAccount.name.ilike(term),
            )
        )
    if insured:
        query = query.filter(CoreAccount.id == insured)
    if state:
        query = query.filter(CorePolicy.state == state)
    if line:
        query = query.filter(CorePolicy.line_of_business == line)
    if date_from:
        query = query.filter(EvidenceLedger.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        query = query.filter(EvidenceLedger.created_at < datetime.combine(date_to + timedelta(days=1), time.min))

    sort_key = sort if sort in SORTS else "newest"
    order = {
        "newest": EvidenceLedger.created_at.desc(),
        "oldest": EvidenceLedger.created_at.asc(),
        "slowest": EvidenceLedger.latency_ms.desc().nullslast(),
        "fastest": EvidenceLedger.latency_ms.asc().nullslast(),
    }[sort_key]
    rows = [_row(*r) for r in query.order_by(order).all()]

    # Outcome is derived for legacy rows, so it is filtered after mapping.
    if outcome:
        rows = [r for r in rows if r["outcome"] == outcome]

    return LedgerPage(
        items=[LedgerRow(**r) for r in rows[offset:offset + limit]],
        total=len(rows),
        limit=limit,
        offset=offset,
    )


@router.get("/{entry_id}", response_model=LedgerDetail)
def get_ledger_entry(entry_id: str, db: Session = Depends(get_db)):
    """Full audit detail for one recorded answer."""
    result = _base_query(db).filter(EvidenceLedger.id == entry_id).first()
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger entry not found")
    entry, policy, account, conversation = result
    return LedgerDetail(
        **_row(entry, policy, account, conversation),
        answer=entry.final_answer,
        product_name=policy.product_name if policy else None,
        evidence=entry.retrieved_evidence or [],
        citations=entry.citations or [],
        guardrail_checks=entry.guardrail_checks or [],
        suggested_questions=entry.suggested_questions or [],
        fallback_reason=entry.fallback_reason,
        retrieval=entry.retrieval or {},
        timings_ms=entry.timings_ms or {},
    )
