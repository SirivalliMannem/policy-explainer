"""Explain API route for AI service."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.explain import (
    ExplainRequest,
    ExplainResponse,
    InterpretationSchema,
    InterpretRequest,
    AttentionAnalysisRequest,
    DocumentQuestionRequest,
    PlainLanguageRequest,
    PlainLanguageResponse,
)
from app.services.explainer_pipeline import ExplainerPipeline
from app.services.attention_analysis import analyze as analyze_attention
from app.services.document_qa import answer_from_document
from app.services.plain_language import explain_clause
from app.services.understanding import QueryInterpreter

router = APIRouter(prefix="/api/explain", tags=["explain"])


@router.post("", response_model=ExplainResponse, status_code=status.HTTP_200_OK)
def explain_question(
    payload: ExplainRequest,
    db: Session = Depends(get_db),
):
    """Execute AI Explainer RAG pipeline on a policy question."""
    return ExplainerPipeline.process_question(
        question=payload.question.strip(),
        policy_id=payload.policy_id.strip(),
        db=db,
        policy_context=payload.policy_context,
        conversation_id=payload.conversation_id,
        previous_question=(payload.previous_question or "").strip() or None,
        interpretation=payload.interpretation,
    )


@router.post("/interpret", response_model=InterpretationSchema)
def interpret_question(
    payload: InterpretRequest,
    db: Session = Depends(get_db),
):
    """Understand a loosely written question: spelling, names, policy numbers, intent and search terms.

    Never answers the question. Falls back to deterministic rules when no language model is available.
    """
    mode = (payload.mode or "").lower() or None
    if mode not in (None, "auto", "rules"):
        mode = None
    return QueryInterpreter.interpret(
        payload.question.strip(),
        db,
        previous_question=(payload.previous_question or "").strip() or None,
        mode=mode,
    ).to_dict()


@router.post("/plain-language", response_model=PlainLanguageResponse)
def plain_language(payload: PlainLanguageRequest):
    """Explain one cited clause in plain words, from its own text only. Never decides coverage."""
    return explain_clause(payload.heading, payload.form_number, payload.text).__dict__


@router.post("/attention-analysis")
def attention_analysis(payload: AttentionAnalysisRequest, db: Session = Depends(get_db)):
    """Classify a flagged question and propose alternatives; only candidates that find evidence are kept."""
    return analyze_attention(
        payload.question.strip(), (payload.policy_id or "").strip() or None, payload.retrieval, db, payload.flag_reason
    )


@router.post("/document")
def explain_document(payload: DocumentQuestionRequest, db: Session = Depends(get_db)):
    """Answer from one uploaded document only, citing its pages or sections."""
    result = answer_from_document(
        payload.document_id, payload.question.strip(), payload.mode, db, (payload.policy_id or "").strip() or None
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return result
