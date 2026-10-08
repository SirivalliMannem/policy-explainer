"""Conversation sessions and pre-RAG question history API endpoints."""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import EmployeeUser, get_current_employee
from app.db.database import get_db
from app.models.conversation import Conversation, ConversationQuestion
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
from app.schemas.explainer import QuestionAnswerResponse
from app.services.ai_client import ai_client
from app.services.ledger.ledger_service import LedgerService

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
    ai_resp = ai_client.explain(
        question=question_text,
        policy_id=conv.policy_id,
        conversation_id=conv.id,
        policy_context=policy_context,
    )

    # 3. Persist Evidence Ledger entry
    LedgerService.record_entry(
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
    )


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
