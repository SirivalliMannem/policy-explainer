"""Schemas for AI Policy Explainer answers, evidence, and citations."""

from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.conversation import PolicyContextSummary


class CitationItem(BaseModel):
    """Citation referencing grounded policy source metadata."""

    model_config = ConfigDict(from_attributes=True)

    source_id: Optional[str] = None
    form_number: Optional[str] = None
    edition: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    heading: Optional[str] = None
    citation_text: Optional[str] = None


class EvidenceItemSchema(BaseModel):
    """Structured evidence item retrieved from policy database."""

    model_config = ConfigDict(from_attributes=True)

    source_type: str  # clause | coverage | form | claim | billing
    source_id: str
    title: str
    form_number: Optional[str] = None
    edition: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    heading: Optional[str] = None
    content: str
    plain_language: Optional[str] = None
    relevance_score: float = 1.0


class QuestionAnswerResponse(BaseModel):
    """Structured answer response produced by the Policy Explainer pipeline."""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: str
    question_id: str
    question: str
    answer: str
    policy_context: PolicyContextSummary
    evidence: list[EvidenceItemSchema] = []
    citations: list[CitationItem] = []
    confidence: str = "high"
    status: str = "answered"
    suggested_questions: list[str] = []


class AIServiceResponse(BaseModel):
    """Structured response returned by AI Service to Backend."""

    model_config = ConfigDict(from_attributes=True)

    question: str
    answer: str
    confidence: str
    status: str
    evidence: list[EvidenceItemSchema] = []
    citations: list[CitationItem] = []
    suggested_questions: list[str] = []
    guardrail_status: str = "passed"
    grounding_context: str = ""
    raw_llm_response: str = ""
