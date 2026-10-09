"""Explain API route for AI service."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.explain import ExplainRequest, ExplainResponse, InterpretationSchema, InterpretRequest
from app.services.explainer_pipeline import ExplainerPipeline
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
