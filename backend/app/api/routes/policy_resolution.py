"""Policy resolution search and resolution API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.core.auth import EmployeeUser, get_current_employee
from app.db.database import get_db
from app.models.policy import CoreAccount, CorePolicy
from app.schemas.policy_resolution import (
    PolicyContextCandidate,
    PolicyResolveRequest,
    QuestionResolution,
    QuestionResolveRequest,
)
from app.models.conversation import Conversation, ConversationQuestion
from app.services.ai_client import ai_client
from app.services.interpretation import asks_about_portfolio, previous_question, remember, understood_text
from app.services.policy_resolver import resolve_policy_from_question
from app.services import small_talk

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


def _recent_policies(db: Session, employee_id: str, limit: int = 3) -> list[CorePolicy]:
    """The policies this employee asked about most recently, newest first."""
    rows = (
        db.query(ConversationQuestion.policy_id, func.max(ConversationQuestion.created_at).label("last_asked"))
        .join(Conversation, Conversation.id == ConversationQuestion.conversation_id)
        .filter(Conversation.employee_id == employee_id, ConversationQuestion.policy_id.isnot(None))
        .group_by(ConversationQuestion.policy_id)
        .order_by(desc("last_asked"))
        .limit(limit)
        .all()
    )
    policies = {p.id: p for p in db.query(CorePolicy).filter(CorePolicy.id.in_([r.policy_id for r in rows])).all()}
    return [policies[r.policy_id] for r in rows if r.policy_id in policies]


def _example_policies(db: Session, employee_id: str) -> list[CorePolicy]:
    """Real policies for example questions: the employee's recent ones, else in-force policies on file."""
    recent = _recent_policies(db, employee_id)
    if recent:
        return recent
    return (
        db.query(CorePolicy)
        .filter(CorePolicy.status == "in_force")
        .order_by(CorePolicy.policy_number, desc(CorePolicy.term_number))
        .limit(2)
        .all()
    )


def _ref(policy: Optional[CorePolicy]) -> Optional[small_talk.PolicyRef]:
    if policy is None:
        return None
    return small_talk.PolicyRef(policy.policy_number, policy.account.name if policy.account else "")


@router.post("/from-question", response_model=QuestionResolution)
def resolve_policy_from_question_text(
    payload: QuestionResolveRequest,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Resolve the policy a free-text question refers to by policy number or policyholder name.

    Returns ``no_reference`` when the question names neither, so the caller can keep the
    conversation's current context or ask the employee which policy to check. ``intent`` is
    ``portfolio`` for questions that count or list policies or customers; those are answered from
    policy records and need no single-policy context.
    """
    question = payload.question.strip()
    conversation = (
        # Only the employee's own conversation lends its previous question as context.
        db.query(Conversation)
        .filter(Conversation.id == payload.conversation_id, Conversation.employee_id == employee.id)
        .first()
        if payload.conversation_id
        else None
    )
    prior = previous_question(conversation.id, conversation.policy_id, db) if conversation else None
    active = db.get(CorePolicy, conversation.policy_id) if conversation and conversation.policy_id else None

    # Greetings, thanks and "what can you do?" get a conversational reply. No language model is
    # called and nothing is recorded: they are not policy questions.
    kind = small_talk.classify(question)
    if kind:
        has_history = bool(
            conversation
            and db.query(ConversationQuestion).filter(ConversationQuestion.conversation_id == conversation.id).count()
        )
        examples = [_ref(p) for p in _example_policies(db, employee.id)]
        reply = small_talk.reply_for(kind, employee.first_name, _ref(active), examples, has_history)
        return QuestionResolution(
            status="no_reference", intent="conversation", reply=reply.text, suggestions=reply.suggestions
        )

    # Understand the question first: "margret chen" becomes "Margaret Chen", "ho 2847 1193" becomes
    # "HO-2847-1193", "polcies" becomes "policies". Without the AI service it falls back to the raw text.
    interpretation = ai_client.interpret(question, prior)
    if conversation:
        remember(conversation.id, question, interpretation)
    understood = understood_text(question, interpretation)

    result = resolve_policy_from_question(understood, db)
    if result.status == "no_reference" and understood != question:
        result = resolve_policy_from_question(question, db)
    intent = "portfolio" if asks_about_portfolio(question, interpretation) else "policy"
    reply: Optional[small_talk.Reply] = None
    suggested: list[CorePolicy] = []
    if result.status == "no_reference":
        if (interpretation or {}).get("intent") == "other":
            # The interpreter judged it unrelated to insurance policies ("what's the weather?").
            intent = "off_topic"
            reply = small_talk.off_topic_reply(_ref(active), [_ref(p) for p in _example_policies(db, employee.id)])
        elif not active:
            suggested = _recent_policies(db, employee.id)
    return QuestionResolution(
        status=result.status,
        intent=intent,
        reply=reply.text if reply else None,
        suggestions=reply.suggestions if reply else [],
        suggested_policies=[_to_candidate(p) for p in suggested],
        interpretation=interpretation,
        matched_on=result.matched_on,
        reference=result.reference,
        policy=_to_candidate(result.policy) if result.policy else None,
        candidates=[_to_candidate(p) for p in result.candidates],
        message=result.message,
    )
