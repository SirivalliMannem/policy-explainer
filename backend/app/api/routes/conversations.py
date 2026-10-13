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
from app.models.policy import CorePolicy
from app.schemas.conversation import (
    ContextCheckResponse,
    ContextSwitchAuditItem,
    ConversationArchiveResponse,
    ConversationContextUpdateRequest,
    ConversationListPage,
    ConversationCreateRequest,
    ConversationResponse,
    ConversationTitleUpdateRequest,
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
from app.services.factual_lookup import (
    execute_factual_lookup,
    is_factual_query,
    is_wording_query,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


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
    """Create a new conversation session with optional initial policy context."""
    policy_id: Optional[str] = None
    policy: Optional[CorePolicy] = None
    if payload and payload.policy_id and payload.policy_id.strip():
        policy_id = payload.policy_id.strip()
        policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first()
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Policy not found",
            )
        validate_employee_authorization(employee, policy)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conversation = Conversation(
        employee_id=employee.id,
        policy_id=policy_id,
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

    return ConversationResponse(
        conversation_id=conversation.id,
        employee_id=conversation.employee_id,
        status=conversation.status,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        policy_context=_build_policy_context(conversation.policy_id, db),
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
        status=conv.status,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        policy_context=_build_policy_context(conv.policy_id, db),
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
        status=conv.status,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        policy_context=_build_policy_context(conv.policy_id, db),
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
    """Update or bind a resolved policy context to the conversation with authorization and switch checks."""
    conv = _get_conversation_or_404(conversation_id, db, employee)
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
    current_policy = db.query(CorePolicy).filter(CorePolicy.id == conv.policy_id).first() if conv.policy_id else None
    check = evaluate_context_transition(current_policy, target_policy)

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
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"You're switching to a different customer. "
                f"You're currently discussing a policy belonging to {check.current_customer.name if check.current_customer else 'Customer A'}. "
                f"The selected policy belongs to {check.target_customer.name}. "
                "Explicit confirmation is required to switch the existing conversation."
            ),
        )

    # 5. Apply context update
    conv.policy_id = policy_id
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
    )

    return ConversationResponse(
        conversation_id=conv.id,
        employee_id=conv.employee_id,
        status=conv.status,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        policy_context=_build_policy_context(conv.policy_id, db),
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
        switch_type="clear_context",
        outcome="success",
    )

    return ConversationResponse(
        conversation_id=conv.id,
        employee_id=conv.employee_id,
        status=conv.status,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        policy_context=None,
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
    # An explicit policy answers this question for one of a customer's several matching policies,
    # without changing the conversation's context; otherwise the conversation's policy is used.
    policy_id = payload.policy_id or conv.policy_id

    # Understand the question first (spelling, names, paraphrase). Reuses the interpretation made
    # when the frontend resolved the policy, so the language model is consulted once per question.
    prior_question = previous_question(conv.id, policy_id, db)
    interpretation = interpret_question(conv.id, question_text, prior_question)
    if payload.policy_id:
        # The same question follows for the customer's other policies: keep its interpretation.
        remember(conv.id, question_text, interpretation)

    # Customer and portfolio questions ("how many policies does X have?") are answered from
    # policy records and do not need, or change, the conversation's single-policy context.
    if not payload.policy_id and asks_about_portfolio(question_text, interpretation, has_selected_policy=bool(conv.policy_id)):
        return _answer_portfolio_question(conv, question_text, db, interpretation, started, employee)

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
    validate_employee_authorization(employee, policy)
    policy_context = _build_policy_context(policy_id, db)

    canonical_question = understood_text(question_text, interpretation)
    is_factual = is_factual_query(canonical_question) or is_factual_query(question_text)
    is_wording = is_wording_query(canonical_question) or is_wording_query(question_text)

    # 1. Pure factual lookup: answer directly from PostgreSQL records without calling Groq or another LLM
    if is_factual and not is_wording:
        return _answer_factual_question(conv, question_text, policy, db, interpretation, started, employee)

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
    outcome = answer_outcome(ai_resp.status, ai_resp.guardrail_status)

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
        guardrail_status=ai_resp.guardrail_status,
        suggested_questions=ai_resp.suggested_questions,
        db=db,
        employee_id=conv.employee_id,
        **_asker_fields(employee),
        outcome=outcome,
        guardrail_checks=[c.model_dump() for c in ai_resp.guardrail_checks],
        model_used=ai_resp.model_used,
        provider=ai_resp.provider,
        is_fallback=ai_resp.is_fallback,
        fallback_reason=ai_resp.fallback_reason,
        latency_ms=latency_ms,
        timings_ms=ai_resp.timings_ms,
        retrieval={**ai_resp.retrieval, "interpretation": ai_resp.interpretation or interpretation},
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
        guardrail_status=ai_resp.guardrail_status,
        guardrail_checks=ai_resp.guardrail_checks,
        outcome=outcome,
        model_used=ai_resp.model_used,
        provider=ai_resp.provider,
        is_fallback=ai_resp.is_fallback,
        fallback_reason=ai_resp.fallback_reason,
        retrieval=ai_resp.retrieval,
        timings_ms=ai_resp.timings_ms,
        latency_ms=latency_ms,
        ledger_id=ledger_entry.id,
        grounding_context_chars=len(ai_resp.grounding_context) if merged_evidence else None,
        interpretation=ai_resp.interpretation or interpretation,
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
) -> QuestionAnswerResponse:
    """Answer a direct factual question from policy schedule records and log it to the Evidence Ledger."""
    lookup_started = time.perf_counter()
    canonical_q = understood_text(question_text, interpretation)
    result = execute_factual_lookup(canonical_q, policy, db)
    if not result:
        result = execute_factual_lookup(question_text, policy, db)

    lookup_ms = int(round((time.perf_counter() - lookup_started) * 1000))
    found = result.found if result else False
    answer_text = (
        result.answer
        if result
        else f"The available records do not contain this information for policy {policy.policy_number}."
    )
    evidence = result.evidence if result else []
    citations = result.citations if result else []
    suggestions = result.suggestions if result else ["What does this policy cover?"]
    grounding_ctx = result.grounding_context if result else "No matching schedule records found."

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    question_record = ConversationQuestion(
        conversation_id=conv.id,
        policy_id=conv.policy_id,
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

    guardrail_checks = [
        GuardrailCheck(
            name="records_grounded",
            status="passed",
            detail="Directly retrieved and verified from core policy schedule records in PostgreSQL.",
        )
    ]

    retrieval = {
        "answer_type": "factual_lookup",
        "fields_matched": result.fields_matched if result else [],
        "records_matched": len(evidence),
        "interpretation": interpretation,
    }

    ledger_entry = LedgerService.record_entry(
        conversation_id=conv.id,
        question_id=question_record.id,
        policy_id=conv.policy_id,
        question=question_text,
        evidence=evidence,
        grounding_context=grounding_ctx,
        raw_llm_response="",
        final_answer=answer_text,
        citations=[c.model_dump() for c in citations],
        confidence="high" if found else "none",
        guardrail_status="passed",
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
        policy_context=_build_policy_context(conv.policy_id, db),
        evidence=evidence,
        citations=citations,
        confidence="high" if found else "none",
        status=question_record.status,
        suggested_questions=suggestions,
        guardrail_status="passed",
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


def _answer_portfolio_question(
    conv: Conversation,
    question_text: str,
    db: Session,
    interpretation: Optional[dict],
    started: float,
    employee: EmployeeUser,
) -> QuestionAnswerResponse:
    """Answer a customer/portfolio question from policy records and record it in the ledger."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    lookup_started = time.perf_counter()
    # The canonical wording carries corrected spelling and exact policyholder names.
    result = answer_portfolio_question(understood_text(question_text, interpretation), db)
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
        policy_context=_build_policy_context(conv.policy_id, db),
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
            policy_context = _build_policy_context(entry.policy_id, db)
            if policy_context or is_portfolio:
                answer = QuestionAnswerResponse(
                    conversation_id=conv.id,
                    question_id=q.id,
                    question=q.question,
                    answer=entry.final_answer,
                    answer_type="portfolio" if is_portfolio else "policy_explanation",
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
