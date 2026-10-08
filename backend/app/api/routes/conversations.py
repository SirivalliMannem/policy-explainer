"""Conversation sessions and pre-RAG question history API endpoints."""

import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import EmployeeUser, get_current_employee
from app.db.database import get_db
from app.models.conversation import Conversation, ConversationQuestion
from app.models.ledger import EvidenceLedger
from app.models.policy import CorePolicy
from app.schemas.conversation import (
    ConversationContextUpdateRequest,
    ConversationCreateRequest,
    ConversationResponse,
    PolicyContextSummary,
    QuestionHistoryItem,
    QuestionSubmitRequest,
    QuestionSubmitResponse,
)
from app.schemas.explainer import ConversationMessage, QuestionAnswerResponse
from app.services.ai_client import ai_client
from app.services.ledger.ledger_service import LedgerService, answer_outcome
from app.services.portfolio import (
    answer_portfolio_question,
    is_portfolio_question,
    portfolio_evidence,
    portfolio_payload,
    portfolio_suggestions,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


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


def _get_conversation_or_404(conversation_id: str, db: Session) -> Conversation:
    """Helper to verify conversation existence or raise 404."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id.strip()).first()
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
    if payload and payload.policy_id and payload.policy_id.strip():
        policy_id = payload.policy_id.strip()
        policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first()
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Policy not found",
            )

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

    return ConversationResponse(
        conversation_id=conversation.id,
        employee_id=conversation.employee_id,
        status=conversation.status,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        policy_context=_build_policy_context(conversation.policy_id, db),
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve conversation metadata and currently bound policy context."""
    conv = _get_conversation_or_404(conversation_id, db)
    return ConversationResponse(
        conversation_id=conv.id,
        employee_id=conv.employee_id,
        status=conv.status,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        policy_context=_build_policy_context(conv.policy_id, db),
    )


@router.post("/{conversation_id}/context", response_model=ConversationResponse)
def set_conversation_context(
    conversation_id: str,
    payload: ConversationContextUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update or bind a resolved policy context to the conversation."""
    conv = _get_conversation_or_404(conversation_id, db)
    policy_id = payload.policy_id.strip()
    policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )

    conv.policy_id = policy_id
    conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(conv)

    return ConversationResponse(
        conversation_id=conv.id,
        employee_id=conv.employee_id,
        status=conv.status,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        policy_context=_build_policy_context(conv.policy_id, db),
    )


@router.delete("/{conversation_id}/context", response_model=ConversationResponse)
def clear_conversation_context(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """Clear the currently bound policy context from the conversation."""
    conv = _get_conversation_or_404(conversation_id, db)
    conv.policy_id = None
    conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(conv)

    return ConversationResponse(
        conversation_id=conv.id,
        employee_id=conv.employee_id,
        status=conv.status,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        policy_context=None,
    )


@router.post(
    "/{conversation_id}/questions",
    response_model=QuestionAnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_question(
    conversation_id: str,
    payload: QuestionSubmitRequest,
    db: Session = Depends(get_db),
):
    """Submit a question in the conversation (Delegates to AI microservice and records Evidence Ledger)."""
    question_text = payload.question.strip() if payload.question else ""
    if not question_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty",
        )

    conv = _get_conversation_or_404(conversation_id, db)

    # Customer and portfolio questions ("how many policies does X have?") are answered from
    # policy records and do not need, or change, the conversation's single-policy context.
    if is_portfolio_question(question_text):
        return _answer_portfolio_question(conv, question_text, db)

    if not conv.policy_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation has no resolved policy context. Policy context is required to ask questions.",
        )

    policy_context = _build_policy_context(conv.policy_id, db)
    if not policy_context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resolved policy associated with conversation no longer exists",
        )

    # The most recent answered question on the same policy lets the AI service resolve follow-ups
    # such as "what endorsement provides that coverage?".
    previous = (
        db.query(ConversationQuestion)
        .filter(
            ConversationQuestion.conversation_id == conv.id,
            ConversationQuestion.policy_id == conv.policy_id,
            ConversationQuestion.status == "answered",
        )
        .order_by(ConversationQuestion.created_at.desc())
        .first()
    )

    # 1. Record incoming question
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    question_record = ConversationQuestion(
        conversation_id=conv.id,
        policy_id=conv.policy_id,
        question=question_text,
        status="processing",
        created_at=now,
    )
    conv.updated_at = now
    db.add(question_record)
    db.commit()
    db.refresh(question_record)

    # 2. Invoke AI Service microservice boundary
    started = time.perf_counter()
    try:
        ai_resp = ai_client.explain(
            question=question_text,
            policy_id=conv.policy_id,
            conversation_id=conv.id,
            policy_context=policy_context,
            previous_question=previous.question if previous else None,
        )
    except HTTPException:
        # Never leave the question stuck in "processing" when the AI service fails.
        question_record.status = "failed"
        db.commit()
        raise
    latency_ms = int(round((time.perf_counter() - started) * 1000))
    outcome = answer_outcome(ai_resp.status, ai_resp.guardrail_status)

    # 3. Persist Evidence Ledger entry
    ledger_entry = LedgerService.record_entry(
        conversation_id=conv.id,
        question_id=question_record.id,
        policy_id=conv.policy_id,
        question=question_text,
        evidence=ai_resp.evidence,
        grounding_context=ai_resp.grounding_context,
        raw_llm_response=ai_resp.raw_llm_response,
        final_answer=ai_resp.answer,
        citations=[c.model_dump() for c in ai_resp.citations],
        confidence=ai_resp.confidence,
        guardrail_status=ai_resp.guardrail_status,
        suggested_questions=ai_resp.suggested_questions,
        db=db,
        employee_id=conv.employee_id,
        outcome=outcome,
        guardrail_checks=[c.model_dump() for c in ai_resp.guardrail_checks],
        model_used=ai_resp.model_used,
        provider=ai_resp.provider,
        is_fallback=ai_resp.is_fallback,
        fallback_reason=ai_resp.fallback_reason,
        latency_ms=latency_ms,
        timings_ms=ai_resp.timings_ms,
        retrieval=ai_resp.retrieval,
    )

    # 4. Update question status
    question_record.status = ai_resp.status
    db.commit()

    # 5. Return structured answer response
    return QuestionAnswerResponse(
        conversation_id=conv.id,
        question_id=question_record.id,
        question=question_text,
        answer=ai_resp.answer,
        policy_context=policy_context,
        evidence=ai_resp.evidence,
        citations=ai_resp.citations,
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
    )


def _answer_portfolio_question(conv: Conversation, question_text: str, db: Session) -> QuestionAnswerResponse:
    """Answer a customer/portfolio question from policy records and record it in the ledger."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    started = time.perf_counter()
    result = answer_portfolio_question(question_text, db)
    lookup_ms = int(round((time.perf_counter() - started) * 1000))

    payload = portfolio_payload(result)
    evidence, citations = portfolio_evidence(result)
    suggestions = portfolio_suggestions(result)
    found = result.scope != "not_found"
    retrieval = {
        "answer_type": "portfolio",
        "portfolio": payload,
        "policies_matched": len(result.policies),
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
    )


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessage])
def get_conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve questions with their recorded answers, so a conversation can be reopened read-only."""
    conv = _get_conversation_or_404(conversation_id, db)
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
                    timings_ms=entry.timings_ms or {},
                    latency_ms=entry.latency_ms,
                    ledger_id=entry.id,
                )
        messages.append(
            ConversationMessage(
                question_id=q.id,
                question=q.question,
                status=q.status,
                policy_id=q.policy_id,
                created_at=q.created_at,
                answer=answer,
            )
        )
    return messages


@router.get("/{conversation_id}/questions", response_model=list[QuestionHistoryItem])
def get_question_history(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve chronological question history for the conversation."""
    _get_conversation_or_404(conversation_id, db)
    questions = (
        db.query(ConversationQuestion)
        .filter(ConversationQuestion.conversation_id == conversation_id)
        .order_by(ConversationQuestion.created_at.asc())
        .all()
    )
    return questions
