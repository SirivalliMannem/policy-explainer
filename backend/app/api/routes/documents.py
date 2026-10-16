"""Documents uploaded into a Policy Explainer conversation, and answers grounded in them.

A document belongs to the conversation and employee that uploaded it: only that employee can see it,
ask about it or detach it, exactly as only they can open the conversation. Only the extracted text is
stored. While a document is attached, the chat answers from it alone; every answer is recorded in the
evidence ledger like any other, with the passages it cites.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import EmployeeUser, get_current_employee
from app.db.database import get_db
from app.models.conversation import Conversation, ConversationQuestion
from app.models.document import UploadedDocument, UploadedDocumentPage
from app.schemas.explainer import CitationItem, QuestionAnswerResponse
from app.services.ai_client import ai_client
from app.services.authorization import UNAUTHORIZED_ROLES
from app.services.conversation_history import asked_by
from app.services.document_extraction import MAX_BYTES, ExtractionError, extract
from app.services.ledger.ledger_service import LedgerService, answer_outcome

router = APIRouter(tags=["documents"])


class DocumentInfo(BaseModel):
    document_id: str
    conversation_id: str
    filename: str
    content_type: str
    size_bytes: int
    page_count: int
    unit: str  # page | section
    char_count: int
    is_active: bool
    created_at: datetime


class DocumentPage(BaseModel):
    document_id: str
    filename: str
    unit: str
    page_number: int
    page_count: int
    text: str


def _info(doc: UploadedDocument) -> DocumentInfo:
    return DocumentInfo(
        document_id=doc.id, conversation_id=doc.conversation_id, filename=doc.filename, content_type=doc.content_type,
        size_bytes=doc.size_bytes, page_count=doc.page_count, unit=doc.unit, char_count=doc.char_count,
        is_active=doc.is_active, created_at=doc.created_at,
    )


def _check_role(employee: EmployeeUser) -> None:
    if (employee.role or "").strip().lower() in UNAUTHORIZED_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee is not authorized to upload documents")


def _own_conversation(conversation_id: str, employee: EmployeeUser, db: Session) -> Conversation:
    from app.api.routes.conversations import _get_conversation_or_404

    return _get_conversation_or_404(conversation_id, db, employee)


def own_document(document_id: str, employee: EmployeeUser, db: Session, conversation_id: Optional[str] = None) -> UploadedDocument:
    """The document if this employee uploaded it (and it is in this conversation); otherwise 404."""
    query = db.query(UploadedDocument).filter(UploadedDocument.id == document_id, UploadedDocument.employee_id == employee.id)
    if conversation_id:
        query = query.filter(UploadedDocument.conversation_id == conversation_id)
    doc = query.first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


@router.post("/api/conversations/{conversation_id}/documents", response_model=DocumentInfo, status_code=status.HTTP_201_CREATED)
async def upload_document(
    conversation_id: str,
    file: UploadFile = File(...),
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Upload a PDF, Word or text document into the conversation; it becomes the attached document."""
    _check_role(employee)
    conv = _own_conversation(conversation_id, employee, db)
    data = await file.read(MAX_BYTES + 1)
    try:
        extracted = extract(file.filename or "", data)
    except ExtractionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # One attached document per conversation: an earlier one is detached (kept, not deleted).
    for earlier in db.query(UploadedDocument).filter(UploadedDocument.conversation_id == conv.id, UploadedDocument.is_active.is_(True)):
        earlier.is_active = False
        earlier.detached_at = now
    doc = UploadedDocument(
        conversation_id=conv.id,
        employee_id=employee.id,
        filename=(file.filename or "document")[-255:],
        content_type=extracted.content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        page_count=len(extracted.pages),
        char_count=sum(len(p) for p in extracted.pages),
        unit=extracted.unit,
        is_active=True,
        created_at=now,
    )
    db.add(doc)
    db.flush()
    for number, text in enumerate(extracted.pages, start=1):
        db.add(UploadedDocumentPage(document_id=doc.id, page_number=number, text=text))
    conv.updated_at = now
    db.commit()
    db.refresh(doc)
    return _info(doc)


@router.get("/api/conversations/{conversation_id}/documents", response_model=list[DocumentInfo])
def list_documents(
    conversation_id: str,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """The documents uploaded into this conversation, the attached one first."""
    conv = _own_conversation(conversation_id, employee, db)
    docs = (
        db.query(UploadedDocument)
        .filter(UploadedDocument.conversation_id == conv.id, UploadedDocument.employee_id == employee.id)
        .order_by(UploadedDocument.is_active.desc(), UploadedDocument.created_at.desc())
        .all()
    )
    return [_info(d) for d in docs]


@router.post("/api/conversations/{conversation_id}/documents/{document_id}/detach", response_model=DocumentInfo)
def detach_document(
    conversation_id: str,
    document_id: str,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Stop answering from the document; the chat answers from the policy again. Nothing is deleted."""
    _own_conversation(conversation_id, employee, db)
    doc = own_document(document_id, employee, db, conversation_id)
    if doc.is_active:
        doc.is_active = False
        doc.detached_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(doc)
    return _info(doc)


@router.get("/api/document-pages/{page_id}", response_model=DocumentPage)
def get_document_page(
    page_id: str,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """The text of one cited page or section, for the source viewer (only the uploader can read it)."""
    page = db.query(UploadedDocumentPage).filter(UploadedDocumentPage.id == page_id).first()
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    doc = own_document(page.document_id, employee, db)
    return DocumentPage(document_id=doc.id, filename=doc.filename, unit=doc.unit, page_number=page.page_number,
                        page_count=doc.page_count, text=page.text)


@router.post("/api/conversations/{conversation_id}/documents/{document_id}/explain",
             response_model=QuestionAnswerResponse, status_code=status.HTTP_201_CREATED)
def explain_document(
    conversation_id: str,
    document_id: str,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Explain the whole document in plain language, citing its pages (asked automatically after upload)."""
    conv = _own_conversation(conversation_id, employee, db)
    doc = own_document(document_id, employee, db, conversation_id)
    return answer_from_document(conv, doc, f"Explain the uploaded document “{doc.filename}” in simple language", "summary",
                                employee, db, time.perf_counter())


def answer_from_document(
    conv: Conversation,
    doc: UploadedDocument,
    question: str,
    mode: str,
    employee: EmployeeUser,
    db: Session,
    started: float,
) -> QuestionAnswerResponse:
    """Answer from the uploaded document only, record it in the ledger and return it."""
    if not doc.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This document is no longer attached to the conversation")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    question_record = ConversationQuestion(conversation_id=conv.id, policy_id=None, question=question, status="processing", created_at=now)
    conv.updated_at = now
    db.add(question_record)
    db.commit()
    db.refresh(question_record)
    try:
        ai = ai_client.explain_document(doc.id, question, mode)
    except HTTPException:
        question_record.status = "failed"
        db.commit()
        raise
    latency_ms = int(round((time.perf_counter() - started) * 1000))
    outcome = answer_outcome(ai.status, ai.guardrail_status)
    retrieval = {**ai.retrieval, "answer_type": "document"}

    from app.api.routes.conversations import _asker_fields

    ledger_entry = LedgerService.record_entry(
        conversation_id=conv.id, question_id=question_record.id, policy_id=None, question=question,
        evidence=ai.evidence, grounding_context=ai.grounding_context, raw_llm_response=ai.raw_llm_response,
        final_answer=ai.answer, citations=[c.model_dump() for c in ai.citations], confidence=ai.confidence,
        guardrail_status=ai.guardrail_status, suggested_questions=[], db=db, employee_id=conv.employee_id,
        **_asker_fields(employee), outcome=outcome, guardrail_checks=[c.model_dump() for c in ai.guardrail_checks],
        model_used=ai.model_used, provider=ai.provider, is_fallback=ai.is_fallback, fallback_reason=ai.fallback_reason,
        latency_ms=latency_ms, timings_ms=ai.timings_ms, retrieval=retrieval,
    )
    question_record.status = ai.status
    db.commit()
    return QuestionAnswerResponse(
        conversation_id=conv.id, question_id=question_record.id, question=question, answer=ai.answer,
        answer_type="document", policy_context=None, evidence=ai.evidence,
        citations=[CitationItem(**c.model_dump()) for c in ai.citations], confidence=ai.confidence, status=ai.status,
        suggested_questions=[], guardrail_status=ai.guardrail_status, guardrail_checks=ai.guardrail_checks,
        outcome=outcome, model_used=ai.model_used, provider=ai.provider, is_fallback=ai.is_fallback,
        fallback_reason=ai.fallback_reason, retrieval=retrieval, timings_ms=ai.timings_ms, latency_ms=latency_ms,
        ledger_id=ledger_entry.id, grounding_context_chars=len(ai.grounding_context) if ai.evidence else None,
        asked_by=asked_by(conv.employee_id, ledger_entry), asked_at=question_record.created_at,
    )
