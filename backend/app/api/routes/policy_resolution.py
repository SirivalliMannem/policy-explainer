"""Policy resolution search and resolution API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.policy import CoreAccount, CorePolicy
from app.schemas.policy_resolution import (
    PolicyContextCandidate,
    PolicyResolveRequest,
    QuestionResolution,
    QuestionResolveRequest,
)
from app.services.policy_resolver import resolve_policy_from_question

router = APIRouter(prefix="/api/policy-resolution", tags=["policy-resolution"])


def _to_candidate(policy: CorePolicy) -> PolicyContextCandidate:
    return PolicyContextCandidate(
        policy_id=policy.id,
        policy_number=policy.policy_number,
        customer_id=policy.account_id,
        customer_name=policy.account.name if policy.account else "",
        line_of_business=policy.line_of_business,
        product_name=policy.product_name,
        status=policy.status,
        effective_date=policy.effective_date,
        expiration_date=policy.expiration_date,
    )


@router.get("/search", response_model=list[PolicyContextCandidate])
def search_policy_context(
    q: Optional[str] = Query(None, description="Search by policy number, customer name, or email"),
    db: Session = Depends(get_db),
):
    """Search for policy contexts matching policy number, customer name, or customer email.

    Returns candidate policy + customer contexts.
    """
    if not q or not q.strip():
        return []

    search_term = f"%{q.strip()}%"

    results = (
        db.query(CorePolicy)
        .join(CoreAccount, CorePolicy.account_id == CoreAccount.id)
        .filter(
            or_(
                CorePolicy.policy_number.ilike(search_term),
                CoreAccount.name.ilike(search_term),
                CoreAccount.email.ilike(search_term),
            )
        )
        .order_by(CorePolicy.effective_date.desc())
        .all()
    )

    return [_to_candidate(policy) for policy in results]


@router.post("/resolve", response_model=PolicyContextCandidate)
def resolve_policy_context(
    payload: PolicyResolveRequest,
    db: Session = Depends(get_db),
):
    """Resolve a specific policy by policy_id and return its policy + customer context."""
    policy_id = payload.policy_id.strip() if payload.policy_id else ""
    if not policy_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )

    policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )

    return _to_candidate(policy)


@router.post("/from-question", response_model=QuestionResolution)
def resolve_policy_from_question_text(
    payload: QuestionResolveRequest,
    db: Session = Depends(get_db),
):
    """Resolve the policy a free-text question refers to by policy number or policyholder name.

    Returns ``no_reference`` when the question names neither, so the caller can keep the
    conversation's current context or ask the employee which policy to check.
    """
    result = resolve_policy_from_question(payload.question, db)
    return QuestionResolution(
        status=result.status,
        matched_on=result.matched_on,
        reference=result.reference,
        policy=_to_candidate(result.policy) if result.policy else None,
        candidates=[_to_candidate(p) for p in result.candidates],
        message=result.message,
    )
