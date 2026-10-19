"""Policy resolution search and resolution API endpoints."""

import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.core.auth import EmployeeUser, get_current_employee
from app.db.database import get_db
from app.models.policy import CoreAccount, CorePolicy
from app.schemas.policy_resolution import (
    CustomerVerification,
    PolicyContextCandidate,
    PolicyResolveRequest,
    QuestionResolution,
    QuestionResolveRequest,
)
from app.models.conversation import Conversation, ConversationQuestion
from app.services.ai_client import ai_client
from app.services.interpretation import asks_about_portfolio, previous_question, remember, understood_text
from app.services.policy_resolver import (
    ResolutionResult,
    current_terms,
    line_hint,
    resolve_policy_from_question,
)
from app.services import small_talk
from app.services import customer_verification
from app.services import conversation_context
from app.services.policy_resolver import find_accounts
from app.schemas.policy_resolution import VerifiedCustomer
from app.services.loss_date import extract_loss_date, term_in_force, term_selection

router = APIRouter(prefix="/api/policy-resolution", tags=["policy-resolution"])

# Matched exactly on a record, never on interpreted wording.
EXACT_IDENTIFIERS = {"policy_number", "claim_number", "account_number", "email", "phone", "vin", "plate"}


from app.services.authorization import validate_employee_authorization


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
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Search for policy contexts matching policy number, customer name, or customer email.

    Returns candidate policy + customer contexts.
    """
    if (employee.role or "").strip().lower() in {"unauthorized", "suspended", "inactive"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee is not authorized to search policy records",
        )

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
    employee: EmployeeUser = Depends(get_current_employee),
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

    validate_employee_authorization(employee, policy)
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
    active_policy_id = payload.policy_id or (conversation.policy_id if conversation else None)
    active_customer_id = payload.customer_id or (conversation.customer_id if conversation else None)
    prior = previous_question(conversation.id, active_policy_id, db) if conversation else None
    active = db.get(CorePolicy, active_policy_id) if active_policy_id else None
    active_cust = db.get(CoreAccount, active_customer_id) if active_customer_id else (active.account if active else None)

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

    # Step 1: Validate customer identity before resolving policy context, retrieving policy
    # evidence, generating suggestions, or invoking the LLM. If the question explicitly names a
    # customer who does not exist in the database, return the customer-not-found response immediately
    # and terminate the current request flow.
    typed = resolve_policy_from_question(question, db)
    early_verification = customer_verification.verify_customer(typed, question, None, None, db)
    # A customer who is on file but has no policies is not "not found": they are said to have none below.
    on_file_without_policies = typed.status == "not_found" and typed.matched_on in ("customer_name", "surname", "first_name")
    if early_verification.status == "not_found" and not on_file_without_policies:
        if conversation:
            customer_verification.remember(conversation.id, question, early_verification)
        return QuestionResolution(
            status="not_found",
            intent="portfolio" if asks_about_portfolio(question, None) else "policy",
            reply=None,
            suggestions=[],
            suggested_policies=[],
            customer_verification=early_verification,
            term_selection=None,
            answer_all=False,
            interpretation=None,
            matched_on=early_verification.matched_on or "customer_name",
            reference=early_verification.reference or typed.reference,
            policy=None,
            candidates=[],
            message=early_verification.message,
        )

    # Understand the question first: "margret chen" becomes "Margaret Chen", "ho 2847 1193" becomes
    # "HO-2847-1193", "polcies" becomes "policies". Without the AI service it falls back to the raw text.
    interpretation = ai_client.interpret(question, prior)
    if conversation:
        remember(conversation.id, question, interpretation)
    understood = understood_text(question, interpretation)

    # Exact identifiers are read from what the employee typed: the interpreter may rewrite them
    # ("margaret.chen@example.com" became "Margaret Chen"), and a rewritten claim number, VIN or
    # phone would match the wrong record or none. Names and loose wording use the understood text.
    if typed.matched_on in EXACT_IDENTIFIERS:
        result = typed
    else:
        result = resolve_policy_from_question(understood, db) if understood != question else typed
        if result.status == "no_reference" and understood != question:
            result = typed

    # The conversation's customer: chosen in the context selector, chosen alone ("What are Elena's
    # policies?"), or the selected policy's customer.
    customer = active_cust
    portfolio_question = asks_about_portfolio(question, interpretation, has_selected_policy=bool(active))
    refers_to_someone = bool(conversation_context.PRONOUN.search(question))
    # Someone named who is not the conversation's customer is never answered from that customer's
    # records: an unknown name fails verification below, a known one resolved above.
    names_someone = bool(customer_verification._named_people(question, interpretation))
    from_context = False
    if result.status == "no_reference" and customer is not None and not names_someone:
        if portfolio_question:
            # "Does she have another policy?", "What are her policies?": that customer's policies.
            from_context = refers_to_someone
        else:
            # "What are the exclusions?", "What about the second one?", "her auto policy".
            follow_up = conversation_context.resolve_follow_up(question, understood, customer, active, db)
            if follow_up is not None:
                result, from_context = follow_up, True

    # A message that only names a customer ("Elena") looks them up: their policies are listed.
    # A customer on file with no policies is said to have none, not reported as not found.
    named_accounts: list = []
    if result.matched_on in ("customer_name", "surname", "first_name"):
        named_accounts, _ = find_accounts(understood, db)
        if not named_accounts:
            named_accounts, _ = find_accounts(question, db)
    customer_lookup = conversation_context.is_name_only(question, named_accounts)
    no_policies = result.status == "not_found" and len({a.id for a in named_accounts}) == 1

    # A date of loss picks the term in force that day: each renewal has its own limits, deductibles
    # and forms. The date is read from what was typed; the interpreter may reword it.
    loss = extract_loss_date(question)
    term_choice: Optional[dict] = None
    if loss:
        if result.status == "resolved" and result.policy:
            term_choice = term_selection(result.policy.policy_number, loss, db)
            if term_choice["status"] == "matched":
                result.policy = db.get(CorePolicy, term_choice["policy_id"])
        elif result.status == "ambiguous":
            in_force = [t for t in (term_in_force(p.policy_number, loss.value, db) for p in result.candidates) if t]
            if len(in_force) == 1:
                term_choice = term_selection(in_force[0].policy_number, loss, db)
                result = ResolutionResult(
                    status="resolved", matched_on=result.matched_on, reference=result.reference, policy=in_force[0]
                )
            elif in_force:
                result.candidates = in_force
            else:
                term_choice = term_selection(result.candidates[0].policy_number, loss, db)
        elif result.status == "no_reference" and active:
            # A follow-up such as "what if the loss was on 1 June 2025?" stays with the selected policy.
            term_choice = term_selection(active.policy_number, loss, db)
            if term_choice["status"] == "matched" and term_choice["policy_id"] != active.id:
                result = ResolutionResult(
                    status="resolved",
                    matched_on="loss_date",
                    reference=active.policy_number,
                    policy=db.get(CorePolicy, term_choice["policy_id"]),
                )

    # Step 1: the customer must exist in the records and be identified uniquely before any policy
    # information is retrieved. The answer, when given, records how its customer was verified.
    if no_policies:
        account = named_accounts[0]
        verification = CustomerVerification(
            status="verified", matched_on=result.matched_on, reference=account.name,
            customers=[VerifiedCustomer(customer_id=account.id, name=account.name, account_number=account.account_number or None)],
            message=f"{account.name} is in the customer records but has no policies on file.",
        )
        result = ResolutionResult(status="no_reference", matched_on=result.matched_on, reference=account.name,
                                  message=verification.message)
    elif from_context:
        # Resolved from the conversation's customer, who is already verified. A reference that picks
        # none of their policies ("the third one" of two) is asked about, not a customer not found.
        verification = CustomerVerification(
            status="verified", matched_on="conversation", reference=customer.name,
            customers=[VerifiedCustomer(customer_id=customer.id, name=customer.name, account_number=customer.account_number or None)],
            message=f"{customer.name}, the customer already selected in this conversation.",
        )
        if result.status == "no_reference":
            # A portfolio follow-up about the conversation's customer.
            result = ResolutionResult(status="no_reference", matched_on="conversation", reference=customer.name)
    else:
        verification = customer_verification.verify_customer(result, understood, interpretation, active, db, customer)
    if conversation:
        customer_verification.remember(conversation.id, question, verification)

    intent = "portfolio" if ((portfolio_question or customer_lookup or no_policies) and verification.status != "not_found") else "policy"
    reply: Optional[small_talk.Reply] = None
    suggested: list[CorePolicy] = []
    status_to_report = result.status
    if verification.status == "not_found":
        status_to_report = "not_found"
        suggested = []
        reply = None
    elif result.status == "no_reference":
        if (interpretation or {}).get("intent") == "other":
            # The interpreter judged it unrelated to insurance policies ("what's the weather?").
            intent = "off_topic"
            reply = small_talk.off_topic_reply(_ref(active), [_ref(p) for p in _example_policies(db, employee.id)])
        elif not active and not customer and intent != "portfolio":
            suggested = _recent_policies(db, employee.id)
    verified = verification.customers[0] if verification.status == "verified" and len(verification.customers) == 1 else None
    return QuestionResolution(
        status=status_to_report,
        intent=intent,
        reply=reply.text if reply else None,
        suggestions=reply.suggestions if reply and status_to_report != "not_found" else [],
        suggested_policies=[_to_candidate(p) for p in suggested] if status_to_report != "not_found" else [],
        customer_verification=verification,
        term_selection=term_choice if status_to_report != "not_found" else None,
        answer_all=result.status == "ambiguous" and len({p.account_id for p in result.candidates}) == 1,
        interpretation=interpretation if status_to_report != "not_found" else None,
        matched_on=verification.matched_on if verification.status == "not_found" else result.matched_on,
        reference=verification.reference if verification.status == "not_found" else result.reference,
        policy=_to_candidate(result.policy) if result.policy and status_to_report != "not_found" else None,
        candidates=[_to_candidate(p) for p in result.candidates] if status_to_report != "not_found" else [],
        message=verification.message if verification.status == "not_found" else result.message,
        customer=verified,
        from_context=from_context,
        customer_lookup=customer_lookup or no_policies,
    )
