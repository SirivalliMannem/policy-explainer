"""Explain API route for AI service."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.explain import ExplainRequest, ExplainResponse
from app.services.explainer_pipeline import ExplainerPipeline

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
    )
