"""Conversation sessions and pre-RAG question history API endpoints."""

import re
import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import EmployeeUser, get_current_employee
from app.db.database import get_db
from app.models.conversation import ContextSwitchAudit, Conversation, ConversationQuestion
from app.models.ledger import EvidenceLedger
from app.models.policy import CoreAccount, CorePolicy
from fi360_shared.agents import POLICY_EXPLAINER
from app.schemas.conversation import (
    ContextCheckResponse,
    ContextSwitchAuditItem,
    ConversationArchiveResponse,
    ConversationContextUpdateRequest,
    ConversationListPage,
    ConversationCreateRequest,
    ConversationResponse,
    ConversationTitleUpdateRequest,
    CustomerContextSummary,
    PolicyContextSummary,
    QuestionHistoryItem,
    QuestionSubmitRequest,
    QuestionSubmitResponse,
)
from app.schemas.dashboard import RecentQuestionItem
from app.schemas.explainer import CitationItem, ConversationMessage, GuardrailCheck, QuestionAnswerResponse
from app.services.ai_client import ai_client
from app.services.authorization import (
    validate_employee_authorization,
    validate_policy_customer_relationship,
)
from app.services.context_switch_service import (
    evaluate_context_transition,
    record_context_switch,
)
from app.services.ledger.ledger_service import LedgerService, answer_outcome
from app.services.recent_questions import recent_questions
from app.services.conversation_history import asked_by, list_conversations
from app.services.interpretation import (
    asks_about_portfolio,
    invalidate_conversation,
    interpret as interpret_question,
    previous_question,
    remember,
    understood_text,
)
from app.services.portfolio import (
    answer_portfolio_question,
    portfolio_evidence,
    portfolio_payload,
    portfolio_suggestions,
)
from app.services.company_guidance import guidance_for_answer, with_guidance_status
from app.services.customer_verification import verification_for_answer, verify_customer
from app.schemas.policy_resolution import CustomerVerification
from app.services.loss_date import extract_loss_date, term_selection
from app.services.multi_part import Part, PartAnswer, answer_endorsement, answer_records, combine, split_question
from app.services.factual_lookup import (
    execute_factual_lookup,
    is_factual_query,
    is_wording_query,
)
from app.services.policy_resolver import (
    current_terms,
    find_accounts,
    line_hint,
    resolve_policy_from_question,
)
from app.services import conversation_context

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _term_for_question(question_text: str, policy: CorePolicy, db: Session) -> Optional[dict]:
    """When the question gives a date of loss: the term of this policy in force that day, or why none was."""
    loss = extract_loss_date(question_text)
    return term_selection(policy.policy_number, loss, db) if loss else None


def _with_term_note(answer: str, term_choice: Optional[dict]) -> str:
    """Start the answer by saying which term it used (or that none was in force), so the record says so too."""
    if not term_choice:
        return answer
    note = term_choice["message"]
    if term_choice["status"] != "matched":
        note += " This answer could not use a term in force on that date."
    return f"{note}\n\n{answer}"


def _asker_fields(employee: EmployeeUser) -> dict:
    """Name and role for the ledger, only when the request identified the employee."""
    if not employee.identified:
        return {"employee_name": None, "employee_role": None}
    return {"employee_name": employee.name, "employee_role": employee.role}


def _build_policy_context(policy_id: Optional[str], db: Session) -> Optional[PolicyContextSummary]:
    """Helper to load and format policy context summary if policy_id is set."""
    if not policy_id:
        return None
    policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first()
    if not policy:
        return None
    return PolicyContextSummary(
        policy_id=policy.id,
        policy_number=policy.policy_number,
        customer_id=policy.account_id,
        customer_name=policy.account.name if policy.account else "",
        line_of_business=policy.line_of_business,
        product_name=policy.product_name,
        status=policy.status,
    )


def _build_customer_context(
    customer_id: Optional[str], policy_id: Optional[str], db: Session
) -> Optional[CustomerContextSummary]:
    """Helper to load and format customer context summary if customer_id or policy_id is set."""
    if customer_id:
        account = db.query(CoreAccount).filter(CoreAccount.id == customer_id).first()
        if account:
            return CustomerContextSummary(
                customer_id=account.id,
                customer_name=account.name,
                account_number=account.account_number or "",
                email=account.email or "",
                policy_count=len(conversation_context.customer_policies(account, db)),
            )
    if policy_id:
        policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first()
        if policy and policy.account:
            return CustomerContextSummary(
                customer_id=policy.account.id,
                customer_name=policy.account.name,
                account_number=policy.account.account_number or "",
                email=policy.account.email or "",
                policy_count=len(conversation_context.customer_policies(policy.account, db)),
            )
    return None


def _get_conversation_or_404(conversation_id: str, db: Session, employee: EmployeeUser) -> Conversation:
    """The conversation if it belongs to the current employee; otherwise 404.

    Another employee's conversation answers exactly like a missing one, so its existence is not
    revealed. Company-wide visibility is The Record's job, not the conversation API's.
    """
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id.strip(), Conversation.employee_id == employee.id)
        .first()
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conv


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: Optional[ConversationCreateRequest] = None,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Create a new conversation session with optional initial policy or customer context."""
    policy_id: Optional[str] = None
    customer_id: Optional[str] = None
    policy: Optional[CorePolicy] = None
    account: Optional[CoreAccount] = None

    if payload and payload.policy_id and payload.policy_id.strip():
        policy_id = payload.policy_id.strip()
        policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first()
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Policy not found",
            )
        validate_employee_authorization(employee, policy)
        customer_id = policy.account_id
    elif payload and payload.customer_id and payload.customer_id.strip():
        customer_id = payload.customer_id.strip()
        account = db.query(CoreAccount).filter(CoreAccount.id == customer_id).first()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conversation = Conversation(
        employee_id=employee.id,
        agent_code=POLICY_EXPLAINER,
        policy_id=policy_id,
        customer_id=customer_id,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    if policy:
        record_context_switch(
            db=db,
            conversation_id=conversation.id,
            employee=employee,
            previous_policy=None,
            new_policy=policy,
            switch_type="initial_selection",
            outcome="success",
        )
    elif customer_id and account:
        record_context_switch(
            db=db,
            conversation_id=conversation.id,
            employee=employee,
            previous_policy=None,
            new_policy=None,
            switch_type="customer_selection",
            outcome="success",
        )

    return ConversationResponse(
        conversation_id=conversation.id,
        employee_id=conversation.employee_id,
        agent_code=conversation.agent_code,
        status=conversation.status,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        policy_context=_build_policy_context(conversation.policy_id, db),
        customer_context=_build_customer_context(conversation.customer_id, conversation.policy_id, db),
    )


@router.get("/recent", response_model=list[RecentQuestionItem])
def list_recent_questions(
    limit: int = Query(15, ge=1, le=50),
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """The current employee's most recently asked questions, newest first (declared before /{id})."""
    return recent_questions(db, limit=limit, employee_id=employee.id)


@router.get("", response_model=ConversationListPage)
def list_my_conversations(
    search: Optional[str] = Query(None, max_length=200, description="Matches the conversation title"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """The current employee's conversations, newest activity first, excluding archived ones.

    Read from stored rows only; titles are the first question or user-assigned rename, never generated.
    """
    return list_conversations(db, employee.id, search=search, limit=limit, offset=offset)


@router.post("/{conversation_id}/archive", response_model=ConversationArchiveResponse)
def archive_conversation(
    conversation_id: str,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Hide a conversation from its owner's lists. Nothing is deleted; ledger entries are untouched."""
    conv = _get_conversation_or_404(conversation_id, db, employee)
    if not conv.is_archived:
        conv.is_archived = True
        conv.archived_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(conv)
    return ConversationArchiveResponse(
        conversation_id=conv.id, is_archived=conv.is_archived, archived_at=conv.archived_at
    )


@router.delete("/{conversation_id}", response_model=ConversationArchiveResponse)
def delete_conversation(
    conversation_id: str,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Delete a conversation by hiding it from employee's lists (soft-delete / archive).

    Evidence Ledger records and context audit transitions remain intact to respect
    mandatory insurance audit-retention requirements.
    """
    return archive_conversation(conversation_id, employee, db)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
def rename_conversation(
    conversation_id: str,
    payload: ConversationTitleUpdateRequest,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Rename a conversation by setting a custom title."""
    conv = _get_conversation_or_404(conversation_id, db, employee)
    conv.title = payload.title.strip()
    conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(conv)
    return ConversationResponse(
        conversation_id=conv.id,
        employee_id=conv.employee_id,
        agent_code=conv.agent_code,
        status=conv.status,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        policy_context=_build_policy_context(conv.policy_id, db),
        customer_context=_build_customer_context(conv.customer_id, conv.policy_id, db),
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Retrieve conversation metadata and currently bound policy context."""
    conv = _get_conversation_or_404(conversation_id, db, employee)
    return ConversationResponse(
        conversation_id=conv.id,
        employee_id=conv.employee_id,
        agent_code=conv.agent_code,
        status=conv.status,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        policy_context=_build_policy_context(conv.policy_id, db),
        customer_context=_build_customer_context(conv.customer_id, conv.policy_id, db),
    )


@router.get("/{conversation_id}/context-check", response_model=ContextCheckResponse)
def check_conversation_context_switch(
    conversation_id: str,
    target_policy_id: str = Query(..., description="Target policy ID to check switch transition"),
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Check whether switching to the target policy requires confirmation or is allowed."""
    conv = _get_conversation_or_404(conversation_id, db, employee)
    target_policy = db.query(CorePolicy).filter(CorePolicy.id == target_policy_id.strip()).first()
    if not target_policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target policy not found",
        )
    validate_employee_authorization(employee, target_policy)
    current_policy = db.query(CorePolicy).filter(CorePolicy.id == conv.policy_id).first() if conv.policy_id else None
    return evaluate_context_transition(current_policy, target_policy)


@router.post("/{conversation_id}/context", response_model=ConversationResponse)
def set_conversation_context(
    conversation_id: str,
    payload: ConversationContextUpdateRequest,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Update or bind a resolved policy or customer context to the conversation with authorization and switch checks."""
    conv = _get_conversation_or_404(conversation_id, db, employee)
    current_policy = db.query(CorePolicy).filter(CorePolicy.id == conv.policy_id).first() if conv.policy_id else None
    current_customer_id = conv.customer_id or (current_policy.account_id if current_policy else None)
    current_customer = db.get(CoreAccount, current_customer_id) if current_customer_id else None

    if payload.policy_id and payload.policy_id.strip():
        policy_id = payload.policy_id.strip()
        target_policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first()
        if not target_policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Policy not found",
            )

        # 1. Authorize employee access to target policy
        validate_employee_authorization(employee, target_policy)

        # 2. Validate customer relationship if customer_id specified
        validate_policy_customer_relationship(target_policy, payload.customer_id)

        # 3. Evaluate transition against active context
        check = evaluate_context_transition(current_policy, target_policy, current_customer)

        # 4. Require explicit confirmation if switching to a different customer
        if check.switch_type == "different_customer" and not payload.confirm_different_customer:
            record_context_switch(
                db=db,
                conversation_id=conv.id,
                employee=employee,
                previous_policy=current_policy,
                new_policy=target_policy,
                switch_type=check.switch_type,
                outcome="rejected",
                reason="Unconfirmed switch to a different customer",
                previous_customer=current_customer,
            )
            current_cust_name = check.current_customer.name if check.current_customer else "Customer A"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"You're switching to a different customer. "
                    f"You're currently discussing {current_cust_name}. "
                    f"The selected policy belongs to {check.target_customer.name}. "
                    "Explicit confirmation is required to switch the existing conversation."
                ),
            )

        # 5. Apply context update
        conv.policy_id = target_policy.id
        conv.customer_id = target_policy.account_id
        conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(conv)

        # 6. Invalidate interpretation cache to prevent cross-policy contamination
        invalidate_conversation(conv.id)

        # 7. Record successful context transition audit
        record_context_switch(
            db=db,
            conversation_id=conv.id,
            employee=employee,
            previous_policy=current_policy,
            new_policy=target_policy,
            switch_type=check.switch_type,
            outcome="success",
            previous_customer=current_customer,
        )

        return ConversationResponse(
            conversation_id=conv.id,
            employee_id=conv.employee_id,
            agent_code=conv.agent_code,
            status=conv.status,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            policy_context=_build_policy_context(conv.policy_id, db),
            customer_context=_build_customer_context(conv.customer_id, conv.policy_id, db),
        )

    elif payload.customer_id and payload.customer_id.strip():
        customer_id = payload.customer_id.strip()
        target_customer = db.query(CoreAccount).filter(CoreAccount.id == customer_id).first()
        if not target_customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )

        if current_customer_id and current_customer_id != target_customer.id and not payload.confirm_different_customer:
            current_cust = db.query(CoreAccount).filter(CoreAccount.id == current_customer_id).first()
            current_name = current_cust.name if current_cust else "Customer A"
            record_context_switch(
                db=db, conversation_id=conv.id, employee=employee, previous_policy=current_policy, new_policy=None,
                switch_type="different_customer", outcome="rejected", reason="Unconfirmed switch to a different customer",
                previous_customer=current_cust, new_customer=target_customer,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"You're switching to a different customer. "
                    f"You're currently discussing {current_name}. "
                    f"The selected customer is {target_customer.name}. "
                    "Explicit confirmation is required to switch the existing conversation."
                ),
            )

        conv.customer_id = target_customer.id
        conv.policy_id = None
        conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(conv)

        invalidate_conversation(conv.id)

        record_context_switch(
            db=db,
            conversation_id=conv.id,
            employee=employee,
            previous_policy=current_policy,
            new_policy=None,
            switch_type="customer_selection" if not current_customer_id else ("different_customer" if current_customer_id != target_customer.id else "same_customer"),
            outcome="success",
            previous_customer=current_customer,
            new_customer=target_customer,
        )

        return ConversationResponse(
            conversation_id=conv.id,
            employee_id=conv.employee_id,
            agent_code=conv.agent_code,
            status=conv.status,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            policy_context=None,
            customer_context=_build_customer_context(conv.customer_id, None, db),
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either policy_id or customer_id must be provided to set conversation context",
        )


@router.delete("/{conversation_id}/context", response_model=ConversationResponse)
def clear_conversation_context(
    conversation_id: str,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Clear the currently bound policy context from the conversation."""
    conv = _get_conversation_or_404(conversation_id, db, employee)
    current_policy = db.query(CorePolicy).filter(CorePolicy.id == conv.policy_id).first() if conv.policy_id else None
    current_customer = conversation_context.active_customer(conv, db)
    conv.policy_id = None
    conv.customer_id = None
    conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(conv)

    invalidate_conversation(conv.id)

    record_context_switch(
        db=db,
        conversation_id=conv.id,
        employee=employee,
        previous_policy=current_policy,
        new_policy=None,
        switch_type="clear_context",
        outcome="success",
        previous_customer=current_customer,
    )

    return ConversationResponse(
        conversation_id=conv.id,
        employee_id=conv.employee_id,
        agent_code=conv.agent_code,
        status=conv.status,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        policy_context=None,
        customer_context=None,
    )


@router.get("/{conversation_id}/context-audit", response_model=list[ContextSwitchAuditItem])
def get_conversation_context_audit(
    conversation_id: str,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Retrieve chronological audit trail of all policy and customer transitions for this conversation."""
    _get_conversation_or_404(conversation_id, db, employee)
    entries = (
        db.query(ContextSwitchAudit)
        .filter(ContextSwitchAudit.conversation_id == conversation_id)
        .order_by(ContextSwitchAudit.timestamp.asc())
        .all()
    )
    return entries


@router.post(
    "/{conversation_id}/questions",
    response_model=QuestionAnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_question(
    conversation_id: str,
    payload: QuestionSubmitRequest,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Submit a question in the conversation (Delegates to AI microservice and records Evidence Ledger)."""
    question_text = payload.question.strip() if payload.question else ""
    if not question_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty",
        )

    conv = _get_conversation_or_404(conversation_id, db, employee)
    started = time.perf_counter()
    # A document attached in this chat: answer from it alone, never from the carrier's records.
    if payload.document_id:
        from app.api.routes.documents import answer_from_document, own_document

        doc = own_document(payload.document_id, employee, db, conv.id)
        return answer_from_document(conv, doc, question_text, "question", employee, db, started)
    active_customer_id = payload.customer_id or conv.customer_id
    policy_id = payload.policy_id or conv.policy_id

    # Validate customer identity BEFORE resolving policy context, retrieving policy evidence,
    # generating suggestions, or invoking the LLM. If the question explicitly names a customer
    # who is not on file, fail customer verification immediately and do not inherit context
    # from a previously selected policy.
    typed_res = resolve_policy_from_question(question_text, db)
    early_cust_verif = verify_customer(typed_res, question_text, None, None, db)
    # A customer on file with no policies is answered with that (their policy list is empty), not as not found.
    on_file_without_policies = typed_res.status == "not_found" and typed_res.matched_on in ("customer_name", "surname", "first_name")
    if (
        early_cust_verif.status == "not_found"
        and not on_file_without_policies
        and not asks_about_portfolio(question_text, None, has_selected_policy=bool(conv.policy_id))
    ):
        return _answer_customer_not_found(conv, question_text, early_cust_verif, db, started, employee)

    # Understand the question first (spelling, names, paraphrase). Reuses the interpretation made
    # when the frontend resolved the policy, so the language model is consulted once per question.
    prior_question = previous_question(conv.id, policy_id, db)
    interpretation = interpret_question(conv.id, question_text, prior_question)
    if payload.policy_id:
        # The same question follows for the customer's other policies: keep its interpretation.
        remember(conv.id, question_text, interpretation)

    # 1. Customer and portfolio questions ("how many policies does X have?", "what are the policies of Sirivalli")
    # are answered from policy records. If an unknown customer is named, answer_portfolio_question returns
    # scope="not_found", policies=[], and does not expose other customers' policies.
    # A message that only names a customer ("Elena"), or names a customer with no policies, lists that
    # customer's policies (or says there are none).
    if not payload.policy_id and (
        asks_about_portfolio(question_text, interpretation, has_selected_policy=bool(conv.policy_id))
        or _is_customer_lookup(question_text, interpretation, db)
    ):
        return _answer_portfolio_question(conv, question_text, db, interpretation, started, employee, default_customer_id=active_customer_id)

    # An explicit policy (one of a customer's several policies, answered in turn) must be the
    # conversation customer's: another customer's policy needs the switch to be confirmed first.
    current_customer = conversation_context.active_customer(conv, db)
    if payload.policy_id and current_customer is not None:
        explicit = db.get(CorePolicy, payload.policy_id)
        if explicit is not None and explicit.account_id != current_customer.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Policy {explicit.policy_number} does not belong to {current_customer.name}, the customer of this "
                    "conversation. Switch the conversation's customer first."
                ),
            )

    # 2. Customer verification check: for policy-specific questions, if the question explicitly names a customer
    # who is not on file, fail customer verification immediately without exposing other customers' policies.
    active_policy = db.get(CorePolicy, conv.policy_id) if conv.policy_id else None
    cust_verif = verify_customer(typed_res, question_text, interpretation, active_policy, db)
    if cust_verif.status == "not_found":
        return _answer_customer_not_found(conv, question_text, cust_verif, db, started, employee)

    # 3. Explicit reference to a different customer in question text requires confirmation if not specified in payload
    if not payload.policy_id:
        if conv.policy_id and active_policy and cust_verif.status == "verified" and cust_verif.matched_on != "conversation":
            if cust_verif.customers and active_policy.account and cust_verif.customers[0].customer_id != active_policy.account_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"You're asking about a policy belonging to {cust_verif.customers[0].name}. "
                        f"You're currently discussing a policy belonging to {active_policy.account.name}. "
                        "Explicit confirmation is required to switch the existing conversation."
                    ),
                )
        elif active_customer_id and cust_verif.status == "verified" and cust_verif.matched_on != "conversation":
            if cust_verif.customers and cust_verif.customers[0].customer_id != active_customer_id:
                active_cust = db.get(CoreAccount, active_customer_id)
                active_cust_name = active_cust.name if active_cust else "another customer"
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"You're asking about a policy belonging to {cust_verif.customers[0].name}. "
                        f"You're currently discussing customer {active_cust_name}. "
                        "Explicit confirmation is required to switch the existing conversation."
                    ),
                )

    if not policy_id and active_customer_id:
        customer = db.get(CoreAccount, active_customer_id)
        if customer:
            acc_policies = db.query(CorePolicy).filter(CorePolicy.account_id == customer.id).all()
            if not acc_policies:
                return _answer_insufficient_evidence_for_customer(conv, question_text, customer, db, started, employee)
            terms = current_terms(acc_policies)
            in_force = [p for p in terms if p.status == "in_force"] or terms
            hint = line_hint(understood_text(question_text, interpretation)) or line_hint(question_text)
            if hint:
                hinted = [p for p in in_force if p.line_of_business == hint]
                if len(hinted) == 1:
                    policy_id = hinted[0].id
                elif len(hinted) > 1:
                    return _answer_ambiguous_customer_policies(conv, question_text, customer, hinted, db, started, employee)
            elif len(in_force) == 1:
                policy_id = in_force[0].id
            else:
                return _answer_ambiguous_customer_policies(conv, question_text, customer, in_force, db, started, employee)

    if not policy_id:
        canonical_q = understood_text(question_text, interpretation)
        res = resolve_policy_from_question(question_text, db)
        if res.status != "resolved" and canonical_q != question_text:
            res = resolve_policy_from_question(canonical_q, db)
        if res.status == "resolved" and res.policy:
            policy_id = res.policy.id

    if not policy_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation has no resolved policy context. Policy context is required to ask questions.",
        )

    policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resolved policy associated with conversation no longer exists",
        )
    # A date of loss: answer from the term in force that day (each renewal has its own limits,
    # deductibles and forms), whichever term the conversation has selected.
    term_choice = _term_for_question(question_text, policy, db)
    if term_choice and term_choice["status"] == "matched" and term_choice["policy_id"] != policy.id:
        policy = db.get(CorePolicy, term_choice["policy_id"])
        policy_id = policy.id
    validate_employee_authorization(employee, policy)

    # Bind the policy the question resolved to as the conversation's context when it has none. An
    # explicit policy (one of a customer's several policies, answered in turn) never changes it.
    if not conv.policy_id and not conv.customer_id and not payload.policy_id:
        conv.policy_id = policy_id
        conv.customer_id = policy.account_id
        conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()

    policy_context = _build_policy_context(policy_id, db)

    canonical_question = understood_text(question_text, interpretation)
    # Several facts in one question ("the deductible, the endorsement and the open claim"): split it,
    # answer each part from its own source and combine the parts into one reply.
    parts = split_question(question_text)
    if parts:
        return _answer_multi_part(
            conv, question_text, parts, policy, policy_context, db, interpretation, prior_question, started, employee, term_choice
        )

    is_factual = is_factual_query(canonical_question) or is_factual_query(question_text)
    is_wording = is_wording_query(canonical_question) or is_wording_query(question_text)

    # 1. Pure factual lookup: answer directly from PostgreSQL records without calling Groq or another LLM
    if is_factual and not is_wording:
        return _answer_factual_question(conv, question_text, policy, db, interpretation, started, employee, term_choice)

    # Combined factual + wording question: retrieve factual details directly and preserve wording explanation via AI pipeline
    factual_result = None
    if is_factual and is_wording:
        factual_result = execute_factual_lookup(canonical_question, policy, db) or execute_factual_lookup(question_text, policy, db)

    # 1. Record incoming question
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    question_record = ConversationQuestion(
        conversation_id=conv.id,
        policy_id=policy_id,
        question=question_text,
        status="processing",
        created_at=now,
    )
    conv.updated_at = now
    db.add(question_record)
    db.commit()
    db.refresh(question_record)

    # 2. Invoke AI Service microservice boundary. The most recent answered question on the same
    # policy lets it resolve follow-ups such as "what endorsement provides that coverage?".
    try:
        ai_resp = ai_client.explain(
            question=question_text,
            policy_id=policy_id,
            conversation_id=conv.id,
            policy_context=policy_context,
            previous_question=prior_question,
            interpretation=interpretation,
        )
    except HTTPException:
        # Never leave the question stuck in "processing" when the AI service fails.
        question_record.status = "failed"
        db.commit()
        raise
    latency_ms = int(round((time.perf_counter() - started) * 1000))

    if factual_result and factual_result.found:
        fact_ev_count = len(factual_result.evidence)
        ai_answer = ai_resp.answer
        if fact_ev_count > 0:
            ai_answer = re.sub(r"\[E(\d+)\]", lambda m: f"[E{int(m.group(1)) + fact_ev_count}]", ai_answer)
        final_answer = f"{factual_result.answer}\n\n{ai_answer}"

        merged_evidence = list(factual_result.evidence) + list(ai_resp.evidence)
        merged_citations = [c.model_dump() if hasattr(c, "model_dump") else c for c in factual_result.citations]
        for c in ai_resp.citations:
            c_dict = c.model_dump() if hasattr(c, "model_dump") else dict(c)
            c_dict["evidence_index"] = c_dict.get("evidence_index", 1) + fact_ev_count
            merged_citations.append(c_dict)
    else:
        final_answer = ai_resp.answer
        merged_evidence = ai_resp.evidence
        merged_citations = [c.model_dump() for c in ai_resp.citations]
    final_answer = _with_term_note(final_answer, term_choice)
    # Company guidance is shown beside the policy answer, never inside it.
    guidance, guidance_check = guidance_for_answer(
        question_text, policy, final_answer, ai_resp.status != "insufficient_evidence", db
    )
    guardrail_checks = list(ai_resp.guardrail_checks) + ([guidance_check] if guidance_check else [])
    guardrail_status = with_guidance_status(ai_resp.guardrail_status, guidance_check)
    outcome = answer_outcome(ai_resp.status, guardrail_status)

    # 3. Persist Evidence Ledger entry
    ledger_entry = LedgerService.record_entry(
        conversation_id=conv.id,
        question_id=question_record.id,
        policy_id=policy_id,
        question=question_text,
        evidence=merged_evidence,
        grounding_context=ai_resp.grounding_context,
        raw_llm_response=ai_resp.raw_llm_response,
        final_answer=final_answer,
        citations=merged_citations,
        confidence=ai_resp.confidence,
        guardrail_status=guardrail_status,
        suggested_questions=ai_resp.suggested_questions,
        db=db,
        employee_id=conv.employee_id,
        **_asker_fields(employee),
        outcome=outcome,
        guardrail_checks=[c.model_dump() for c in guardrail_checks],
        model_used=ai_resp.model_used,
        provider=ai_resp.provider,
        is_fallback=ai_resp.is_fallback,
        fallback_reason=ai_resp.fallback_reason,
        latency_ms=latency_ms,
        timings_ms=ai_resp.timings_ms,
        retrieval={
            **ai_resp.retrieval,
            "interpretation": ai_resp.interpretation or interpretation,
            "customer_verification": verification_for_answer(conv.id, question_text, policy),
            "term_selection": term_choice,
            "company_guidance": guidance,
        },
    )

    # 4. Update question status
    question_record.status = ai_resp.status
    db.commit()

    citation_items = [
        CitationItem(**c) if isinstance(c, dict) else c for c in merged_citations
    ]

    # 5. Return structured answer response
    return QuestionAnswerResponse(
        conversation_id=conv.id,
        question_id=question_record.id,
        question=question_text,
        answer=final_answer,
        policy_context=policy_context,
        evidence=merged_evidence,
        citations=citation_items,
        confidence=ai_resp.confidence,
        status=ai_resp.status,
        suggested_questions=ai_resp.suggested_questions,
        guardrail_status=guardrail_status,
        guardrail_checks=guardrail_checks,
        outcome=outcome,
        model_used=ai_resp.model_used,
        provider=ai_resp.provider,
        is_fallback=ai_resp.is_fallback,
        fallback_reason=ai_resp.fallback_reason,
        retrieval={
            **ai_resp.retrieval,
            "customer_verification": verification_for_answer(conv.id, question_text, policy),
            "term_selection": term_choice,
            "company_guidance": guidance,
        },
        timings_ms=ai_resp.timings_ms,
        latency_ms=latency_ms,
        ledger_id=ledger_entry.id,
        grounding_context_chars=len(ai_resp.grounding_context) if merged_evidence else None,
        interpretation=ai_resp.interpretation or interpretation,
        asked_by=asked_by(conv.employee_id, ledger_entry),
        asked_at=question_record.created_at,
    )


def _answer_multi_part(
    conv: Conversation,
    question_text: str,
    parts: list[Part],
    policy: CorePolicy,
    policy_context: PolicyContextSummary,
    db: Session,
    interpretation: Optional[dict],
    prior_question: Optional[str],
    started: float,
    employee: EmployeeUser,
    term_choice: Optional[dict] = None,
) -> QuestionAnswerResponse:
    """Answer each part of a several-facts question from its own source and combine them into one reply.

    Facts come from the policy records, endorsements from the attached forms, and only the parts about
    what the wording means go to clause search and the language model, asked together in one call.
    """
    lookup_started = time.perf_counter()
    answers: list[Optional[PartAnswer]] = []
    for part in parts:
        if part.source == "records":
            answers.append(answer_records(part, policy, db))
        elif part.source == "forms":
            answers.append(answer_endorsement(part, policy, db))
        else:
            answers.append(None)  # answered by the language model below
    lookup_ms = int(round((time.perf_counter() - lookup_started) * 1000))

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    question_record = ConversationQuestion(
        conversation_id=conv.id, policy_id=policy.id, question=question_text, status="processing", created_at=now
    )
    conv.updated_at = now
    db.add(question_record)
    db.commit()
    db.refresh(question_record)

    wording_parts = [p for p in parts if p.source == "wording"]
    ai_resp = None
    wording_answer: Optional[PartAnswer] = None
    if wording_parts:
        wording_question = " ".join(p.text.rstrip("?. ") + "?" for p in wording_parts)
        try:
            ai_resp = ai_client.explain(
                question=wording_question,
                policy_id=policy.id,
                conversation_id=conv.id,
                policy_context=policy_context,
                previous_question=prior_question,
                interpretation=None,
            )
        except HTTPException:
            question_record.status = "failed"
            db.commit()
            raise
        ai_evidence = list(ai_resp.evidence)
        for i, item in enumerate(ai_evidence, start=1):
            item.evidence_index = item.evidence_index or i
        wording_answer = PartAnswer(
            wording_parts[0], ai_resp.answer, ai_evidence, list(ai_resp.citations),
            found=ai_resp.status != "insufficient_evidence",
        )

    # The parts in the order they were asked; the wording parts share one model answer.
    ordered: list[PartAnswer] = []
    for part, answer in zip(parts, answers):
        if answer is not None:
            ordered.append(answer)
        elif wording_answer is not None and part is wording_parts[0]:
            ordered.append(wording_answer)
    answer_text, evidence, citations = combine(ordered)
    answer_text = _with_term_note(answer_text, term_choice)

    found = any(a.found for a in ordered)
    status_value = "answered" if found else "insufficient_evidence"
    guardrail_checks: list[GuardrailCheck] = []
    if any(p.source in ("records", "forms") for p in parts):
        guardrail_checks.append(GuardrailCheck(
            name="records_grounded",
            status="passed",
            detail="Facts and endorsements were read directly from the policy records and attached forms.",
        ))
    if ai_resp is not None:
        guardrail_checks.extend(ai_resp.guardrail_checks)
    guardrail_status = ai_resp.guardrail_status if ai_resp is not None and ai_resp.guardrail_status in ("flagged", "failed") else "passed"
    guidance, guidance_check = guidance_for_answer(question_text, policy, answer_text, found, db)
    if guidance_check:
        guardrail_checks.append(guidance_check)
    guardrail_status = with_guidance_status(guardrail_status, guidance_check)
    outcome = answer_outcome(status_value, guardrail_status)
    confidence = ai_resp.confidence if ai_resp is not None else ("high" if found else "none")
    model_used = ai_resp.model_used if ai_resp is not None else "none (records)"
    provider = ai_resp.provider if ai_resp is not None else "none"
    timings = {**(ai_resp.timings_ms if ai_resp is not None else {}), "records_lookup": lookup_ms}
    timings.setdefault("retrieval", lookup_ms)
    retrieval = {
        **(ai_resp.retrieval if ai_resp is not None else {}),
        # All parts from the records reads as a record answer; any wording part makes it a mixed answer.
        "answer_type": "multi_part" if ai_resp is not None else "factual_lookup",
        "parts": [{"label": a.part.label, "question": a.part.text, "source": a.part.source, "found": a.found} for a in ordered],
        "interpretation": interpretation,
        "customer_verification": verification_for_answer(conv.id, question_text, policy),
        "term_selection": term_choice,
        "company_guidance": guidance,
    }
    grounding_ctx = ai_resp.grounding_context if ai_resp is not None else "Answered from the policy records and attached forms."
    latency_ms = int(round((time.perf_counter() - started) * 1000))

    question_record.status = status_value
    ledger_entry = LedgerService.record_entry(
        conversation_id=conv.id,
        question_id=question_record.id,
        policy_id=policy.id,
        question=question_text,
        evidence=evidence,
        grounding_context=grounding_ctx,
        raw_llm_response=ai_resp.raw_llm_response if ai_resp is not None else "",
        final_answer=answer_text,
        citations=[c.model_dump() for c in citations],
        confidence=confidence,
        guardrail_status=guardrail_status,
        suggested_questions=ai_resp.suggested_questions if ai_resp is not None else [],
        db=db,
        employee_id=conv.employee_id,
        **_asker_fields(employee),
        outcome=outcome,
        guardrail_checks=[c.model_dump() for c in guardrail_checks],
        model_used=model_used,
        provider=provider,
        is_fallback=bool(ai_resp.is_fallback) if ai_resp is not None else False,
        fallback_reason=ai_resp.fallback_reason if ai_resp is not None else None,
        latency_ms=latency_ms,
        timings_ms=timings,
        retrieval=retrieval,
    )
    db.commit()

    return QuestionAnswerResponse(
        conversation_id=conv.id,
        question_id=question_record.id,
        question=question_text,
        answer=answer_text,
        policy_context=_build_policy_context(policy.id, db),
        evidence=evidence,
        citations=citations,
        confidence=confidence,
        status=status_value,
        suggested_questions=ai_resp.suggested_questions if ai_resp is not None else [],
        guardrail_status=guardrail_status,
        guardrail_checks=guardrail_checks,
        outcome=outcome,
        model_used=model_used,
        provider=provider,
        is_fallback=bool(ai_resp.is_fallback) if ai_resp is not None else False,
        fallback_reason=ai_resp.fallback_reason if ai_resp is not None else None,
        retrieval=retrieval,
        timings_ms=timings,
        latency_ms=latency_ms,
        ledger_id=ledger_entry.id,
        grounding_context_chars=len(grounding_ctx) if evidence else None,
        interpretation=interpretation,
        asked_by=asked_by(conv.employee_id, ledger_entry),
        asked_at=question_record.created_at,
    )


def _answer_factual_question(
    conv: Conversation,
    question_text: str,
    policy: CorePolicy,
    db: Session,
    interpretation: Optional[dict],
    started: float,
    employee: EmployeeUser,
    term_choice: Optional[dict] = None,
) -> QuestionAnswerResponse:
    """Answer a direct factual question from policy schedule records and log it to the Evidence Ledger."""
    lookup_started = time.perf_counter()
    canonical_q = understood_text(question_text, interpretation)
    result = execute_factual_lookup(canonical_q, policy, db)
    if not result:
        result = execute_factual_lookup(question_text, policy, db)

    lookup_ms = int(round((time.perf_counter() - lookup_started) * 1000))
    found = result.found if result else False
    answer_text = _with_term_note(
        result.answer
        if result
        else f"The available records do not contain this information for policy {policy.policy_number}.",
        term_choice,
    )
    evidence = result.evidence if result else []
    citations = result.citations if result else []
    suggestions = result.suggestions if result else ["What does this policy cover?"]
    grounding_ctx = result.grounding_context if result else "No matching schedule records found."

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    question_record = ConversationQuestion(
        conversation_id=conv.id,
        policy_id=policy.id,
        question=question_text,
        status="answered" if found else "insufficient_evidence",
        created_at=now,
    )
    conv.updated_at = now
    db.add(question_record)
    db.commit()
    db.refresh(question_record)

    latency_ms = int(round((time.perf_counter() - started) * 1000))

    guardrail_checks = [
        GuardrailCheck(
            name="records_grounded",
            status="passed",
            detail="Directly retrieved and verified from core policy schedule records in PostgreSQL.",
        )
    ]
    guidance, guidance_check = guidance_for_answer(question_text, policy, answer_text, found, db)
    if guidance_check:
        guardrail_checks.append(guidance_check)
    guardrail_status = with_guidance_status("passed", guidance_check)
    outcome = answer_outcome(question_record.status, guardrail_status)

    retrieval = {
        "answer_type": "factual_lookup",
        "fields_matched": result.fields_matched if result else [],
        "records_matched": len(evidence),
        "interpretation": interpretation,
        "customer_verification": verification_for_answer(conv.id, question_text, policy),
        "term_selection": term_choice,
        "company_guidance": guidance,
    }

    ledger_entry = LedgerService.record_entry(
        conversation_id=conv.id,
        question_id=question_record.id,
        policy_id=policy.id,
        question=question_text,
        evidence=evidence,
        grounding_context=grounding_ctx,
        raw_llm_response="",
        final_answer=answer_text,
        citations=[c.model_dump() for c in citations],
        confidence="high" if found else "none",
        guardrail_status=guardrail_status,
        suggested_questions=suggestions,
        db=db,
        employee_id=conv.employee_id,
        **_asker_fields(employee),
        outcome=outcome,
        guardrail_checks=[c.model_dump() for c in guardrail_checks],
        model_used="none (records)",
        provider="none",
        is_fallback=False,
        latency_ms=latency_ms,
        timings_ms={"retrieval": lookup_ms},
        retrieval=retrieval,
    )

    return QuestionAnswerResponse(
        conversation_id=conv.id,
        question_id=question_record.id,
        question=question_text,
        answer=answer_text,
        policy_context=_build_policy_context(policy.id, db),
        evidence=evidence,
        citations=citations,
        confidence="high" if found else "none",
        status=question_record.status,
        suggested_questions=suggestions,
        guardrail_status=guardrail_status,
        guardrail_checks=guardrail_checks,
        outcome=outcome,
        model_used="none (records)",
        provider="none",
        is_fallback=False,
        fallback_reason=None,
        retrieval=retrieval,
        timings_ms={"retrieval": lookup_ms},
        latency_ms=latency_ms,
        ledger_id=ledger_entry.id,
        grounding_context_chars=len(grounding_ctx) if evidence else None,
        interpretation=interpretation,
        asked_by=asked_by(conv.employee_id, ledger_entry),
        asked_at=question_record.created_at,
    )


def _answer_customer_not_found(
    conv: Conversation,
    question_text: str,
    verification: CustomerVerification,
    db: Session,
    started: float,
    employee: EmployeeUser,
) -> QuestionAnswerResponse:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    question_record = ConversationQuestion(
        conversation_id=conv.id,
        policy_id=None,
        question=question_text,
        status="insufficient_evidence",
        created_at=now,
    )
    conv.updated_at = now
    db.add(question_record)
    db.commit()
    db.refresh(question_record)

    latency_ms = int(round((time.perf_counter() - started) * 1000))
    ledger_entry = LedgerService.record_entry(
        conversation_id=conv.id,
        question_id=question_record.id,
        policy_id=None,
        question=question_text,
        evidence=[],
        grounding_context="Customer verification failed; named customer not found in customer records.",
        raw_llm_response="",
        final_answer=verification.message,
        citations=[],
        confidence="none",
        guardrail_status="not_applicable",
        suggested_questions=[],
        db=db,
        employee_id=conv.employee_id,
        **_asker_fields(employee),
        outcome="insufficient_evidence",
        guardrail_checks=[],
        model_used="none",
        provider="none",
        is_fallback=False,
        latency_ms=latency_ms,
        retrieval={
            "answer_type": "customer_verification_failed",
            "customer_verification": verification.model_dump(),
            "policies_matched": 0,
        },
    )

    return QuestionAnswerResponse(
        conversation_id=conv.id,
        question_id=question_record.id,
        question=question_text,
        status="insufficient_evidence",
        answer=verification.message,
        evidence=[],
        citations=[],
        confidence="none",
        confidence_percent=None,
        confidence_criteria=None,
        guardrail_status="not_applicable",
        guardrail_checks=[],
        suggested_questions=[],
        retrieval={
            "answer_type": "customer_verification_failed",
            "customer_verification": verification.model_dump(),
            "policies_matched": 0,
        },
        ledger_id=ledger_entry.id,
        created_at=question_record.created_at,
        asked_by=asked_by(conv.employee_id, ledger_entry),
        asked_at=question_record.created_at,
        latency_ms=latency_ms,
    )


def _answer_insufficient_evidence_for_customer(
    conv: Conversation,
    question_text: str,
    customer: CoreAccount,
    db: Session,
    started: float,
    employee: EmployeeUser,
) -> QuestionAnswerResponse:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    question_record = ConversationQuestion(
        conversation_id=conv.id,
        policy_id=None,
        question=question_text,
        status="insufficient_evidence",
        created_at=now,
    )
    conv.updated_at = now
    db.add(question_record)
    db.commit()
    db.refresh(question_record)

    latency_ms = int(round((time.perf_counter() - started) * 1000))
    answer_text = f"No policies are on file for {customer.name}."
    ledger_entry = LedgerService.record_entry(
        conversation_id=conv.id,
        question_id=question_record.id,
        policy_id=None,
        question=question_text,
        evidence=[],
        grounding_context=f"No policy records on file for customer {customer.name}.",
        raw_llm_response="",
        final_answer=answer_text,
        citations=[],
        confidence="none",
        guardrail_status="not_applicable",
        suggested_questions=[],
        db=db,
        employee_id=conv.employee_id,
        **_asker_fields(employee),
        outcome="insufficient_evidence",
        guardrail_checks=[],
        model_used="none",
        provider="none",
        is_fallback=True,
        latency_ms=latency_ms,
        retrieval={
            "answer_type": "no_policies_for_customer",
            "customer_id": customer.id,
            "customer_name": customer.name,
            "policies_matched": 0,
        },
    )

    return QuestionAnswerResponse(
        conversation_id=conv.id,
        question_id=question_record.id,
        question=question_text,
        status="insufficient_evidence",
        answer=answer_text,
        evidence=[],
        citations=[],
        confidence="none",
        confidence_percent=None,
        confidence_criteria=None,
        guardrail_status="not_applicable",
        guardrail_checks=[],
        suggested_questions=[],
        retrieval={
            "answer_type": "no_policies_for_customer",
            "customer_id": customer.id,
            "customer_name": customer.name,
            "policies_matched": 0,
        },
        ledger_id=ledger_entry.id,
        created_at=question_record.created_at,
        asked_by=asked_by(conv.employee_id, ledger_entry),
        asked_at=question_record.created_at,
        latency_ms=latency_ms,
    )


def _answer_ambiguous_customer_policies(
    conv: Conversation,
    question_text: str,
    customer: CoreAccount,
    policies: list[CorePolicy],
    db: Session,
    started: float,
    employee: EmployeeUser,
) -> QuestionAnswerResponse:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    question_record = ConversationQuestion(
        conversation_id=conv.id,
        policy_id=None,
        question=question_text,
        status="needs_input",
        created_at=now,
    )
    conv.updated_at = now
    db.add(question_record)
    db.commit()
    db.refresh(question_record)

    latency_ms = int(round((time.perf_counter() - started) * 1000))
    policy_nums = [f"{p.policy_number} ({p.line_of_business.replace('_', ' ')})" for p in policies]
    answer_text = f"{customer.name} has {len(policies)} policies on file: {', '.join(policy_nums)}. Please select which policy you would like to ask about."
    ledger_entry = LedgerService.record_entry(
        conversation_id=conv.id,
        question_id=question_record.id,
        policy_id=None,
        question=question_text,
        evidence=[],
        grounding_context=f"Multiple policies found for customer {customer.name}; waiting for policy selection.",
        raw_llm_response="",
        final_answer=answer_text,
        citations=[],
        confidence="none",
        guardrail_status="not_applicable",
        suggested_questions=[f"What does {p.policy_number} cover?" for p in policies[:3]],
        db=db,
        employee_id=conv.employee_id,
        **_asker_fields(employee),
        outcome="needs_review",
        guardrail_checks=[],
        model_used="none",
        provider="none",
        is_fallback=False,
        latency_ms=latency_ms,
        retrieval={
            "answer_type": "ambiguous_customer_policies",
            "customer_id": customer.id,
            "customer_name": customer.name,
            "policies_matched": len(policies),
        },
    )

    return QuestionAnswerResponse(
        conversation_id=conv.id,
        question_id=question_record.id,
        question=question_text,
        status="needs_input",
        answer=answer_text,
        evidence=[],
        citations=[],
        confidence="none",
        confidence_percent=None,
        confidence_criteria=None,
        guardrail_status="not_applicable",
        guardrail_checks=[],
        suggested_questions=[f"What does {p.policy_number} cover?" for p in policies[:3]],
        retrieval={
            "answer_type": "ambiguous_customer_policies",
            "customer_id": customer.id,
            "customer_name": customer.name,
            "policies_matched": len(policies),
            "policies": [
                {
                    "policy_id": p.id,
                    "policy_number": p.policy_number,
                    "line_of_business": p.line_of_business,
                }
                for p in policies
            ],
        },
        ledger_id=ledger_entry.id,
        created_at=question_record.created_at,
        asked_by=asked_by(conv.employee_id, ledger_entry),
        asked_at=question_record.created_at,
        latency_ms=latency_ms,
    )


def _is_customer_lookup(question_text: str, interpretation: Optional[dict], db: Session) -> bool:
    """True for a message that only names a customer ("Elena", "look up David Chen") or names a
    customer on file who has no policies: either is answered with that customer's policy list."""
    canonical = understood_text(question_text, interpretation)
    accounts, _ = find_accounts(canonical, db)
    if not accounts and canonical != question_text:
        accounts, _ = find_accounts(question_text, db)
    if not accounts:
        return False
    if conversation_context.is_name_only(question_text, accounts):
        return True
    unique = {a.id for a in accounts}
    return len(unique) == 1 and not db.query(CorePolicy).filter(CorePolicy.account_id.in_(unique)).count()


def _answer_portfolio_question(
    conv: Conversation,
    question_text: str,
    db: Session,
    interpretation: Optional[dict],
    started: float,
    employee: EmployeeUser,
    default_customer_id: Optional[str] = None,
) -> QuestionAnswerResponse:
    """Answer a customer/portfolio question from policy records and record it in the ledger."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    lookup_started = time.perf_counter()
    default_acc = db.get(CoreAccount, default_customer_id) if default_customer_id else None
    # The canonical wording carries corrected spelling and exact policyholder names.
    result = answer_portfolio_question(understood_text(question_text, interpretation), db, default_account=default_acc)
    lookup_ms = int(round((time.perf_counter() - lookup_started) * 1000))

    payload = portfolio_payload(result)
    evidence, citations = portfolio_evidence(result)
    suggestions = portfolio_suggestions(result)
    found = result.scope != "not_found"
    retrieval = {
        "answer_type": "portfolio",
        "portfolio": payload,
        "policies_matched": len(result.policies),
        "interpretation": interpretation,
        "customer_verification": verification_for_answer(conv.id, question_text, None),
    }

    question_record = ConversationQuestion(
        conversation_id=conv.id,
        policy_id=None,
        question=question_text,
        status="answered" if found else "insufficient_evidence",
        created_at=now,
    )
    conv.updated_at = now
    db.add(question_record)
    db.commit()
    db.refresh(question_record)

    latency_ms = int(round((time.perf_counter() - started) * 1000))
    outcome = "answered" if found else "insufficient_evidence"
    ledger_entry = LedgerService.record_entry(
        conversation_id=conv.id,
        question_id=question_record.id,
        policy_id=None,
        question=question_text,
        evidence=evidence,
        grounding_context="Answered from policy records (core_policy, core_account); no policy wording involved.",
        raw_llm_response="",
        final_answer=result.answer,
        citations=citations,
        # Record lookups are exact rather than inferred; there is nothing to grade.
        confidence="high" if found else "none",
        guardrail_status="not_applicable",
        suggested_questions=suggestions,
        db=db,
        employee_id=conv.employee_id,
        **_asker_fields(employee),
        outcome=outcome,
        guardrail_checks=[],
        model_used="none",
        provider="none",
        is_fallback=False,
        latency_ms=latency_ms,
        timings_ms={"retrieval": lookup_ms},
        retrieval=retrieval,
    )

    return QuestionAnswerResponse(
        conversation_id=conv.id,
        question_id=question_record.id,
        question=question_text,
        answer=result.answer,
        answer_type="portfolio",
        portfolio=payload,
        policy_context=_build_policy_context(conv.policy_id, db) if found else None,
        evidence=evidence,
        citations=citations,
        confidence="high" if found else "none",
        status=question_record.status,
        suggested_questions=suggestions,
        guardrail_status="not_applicable",
        guardrail_checks=[],
        outcome=outcome,
        model_used="none",
        provider="none",
        is_fallback=False,
        retrieval=retrieval,
        timings_ms={"retrieval": lookup_ms},
        latency_ms=latency_ms,
        ledger_id=ledger_entry.id,
        interpretation=interpretation,
        asked_by=asked_by(conv.employee_id, ledger_entry),
        asked_at=question_record.created_at,
    )


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessage])
def get_conversation_messages(
    conversation_id: str,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Retrieve questions with their recorded answers, so a conversation can be reopened read-only."""
    conv = _get_conversation_or_404(conversation_id, db, employee)
    questions = (
        db.query(ConversationQuestion)
        .filter(ConversationQuestion.conversation_id == conv.id)
        .order_by(ConversationQuestion.created_at.asc())
        .all()
    )
    entries = {
        entry.question_id: entry
        for entry in db.query(EvidenceLedger).filter(EvidenceLedger.conversation_id == conv.id).all()
    }

    messages: list[ConversationMessage] = []
    for q in questions:
        entry = entries.get(q.id)
        answer = None
        if entry is not None:
            retrieval = entry.retrieval or {}
            is_portfolio = retrieval.get("answer_type") == "portfolio"
            is_document = retrieval.get("answer_type") == "document"
            policy_context = _build_policy_context(entry.policy_id, db)
            if policy_context or is_portfolio or is_document:
                answer = QuestionAnswerResponse(
                    conversation_id=conv.id,
                    question_id=q.id,
                    question=q.question,
                    answer=entry.final_answer,
                    answer_type="portfolio" if is_portfolio else "document" if is_document else "policy_explanation",
                    portfolio=retrieval.get("portfolio") if is_portfolio else None,
                    policy_context=policy_context,
                    evidence=entry.retrieved_evidence or [],
                    citations=entry.citations or [],
                    confidence=entry.confidence,
                    status=q.status,
                    suggested_questions=entry.suggested_questions or [],
                    guardrail_status=entry.guardrail_status,
                    guardrail_checks=entry.guardrail_checks or [],
                    outcome=entry.outcome or answer_outcome(q.status, entry.guardrail_status),
                    model_used=entry.model_used or "unknown",
                    provider=entry.provider or "unknown",
                    is_fallback=bool(entry.is_fallback),
                    fallback_reason=entry.fallback_reason,
                    retrieval=retrieval,
                    interpretation=retrieval.get("interpretation"),
                    timings_ms=entry.timings_ms or {},
                    latency_ms=entry.latency_ms,
                    ledger_id=entry.id,
                    grounding_context_chars=(
                        len(entry.grounding_context)
                        if entry.retrieved_evidence and entry.grounding_context and not is_portfolio
                        else None
                    ),
                    asked_by=asked_by(conv.employee_id, entry),
                    asked_at=q.created_at,
                )
        messages.append(
            ConversationMessage(
                question_id=q.id,
                question=q.question,
                status=q.status,
                policy_id=q.policy_id,
                created_at=q.created_at,
                asked_by=asked_by(conv.employee_id, entry),
                answer=answer,
            )
        )
    return messages


@router.get("/{conversation_id}/questions", response_model=list[QuestionHistoryItem])
def get_question_history(
    conversation_id: str,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Retrieve chronological question history for the conversation."""
    _get_conversation_or_404(conversation_id, db, employee)
    questions = (
        db.query(ConversationQuestion)
        .filter(ConversationQuestion.conversation_id == conversation_id)
        .order_by(ConversationQuestion.created_at.asc())
        .all()
    )
    return questions
