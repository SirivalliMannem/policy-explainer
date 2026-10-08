"""Pydantic schemas for the Explain API endpoints."""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.policy_context import PolicyContextSummary


class CitationItem(BaseModel):
    """Citation reference pointing to verified policy evidence."""

    source_id: Optional[str] = None
    form_number: Optional[str] = None
    edition: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    heading: Optional[str] = None
    citation_text: Optional[str] = None


class EvidenceItemSchema(BaseModel):
    """Individual evidence record retrieved from policy context."""

    source_type: str
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


class ExplainRequest(BaseModel):
    """Request payload sent by Backend to AI Service to explain a question."""

    question: str = Field(..., min_length=1, description="Question text submitted by employee")
    policy_id: str = Field(..., min_length=1, description="Resolved policy UUID")
    conversation_id: Optional[str] = Field(None, description="Optional conversation UUID for logging")
    policy_context: Optional[PolicyContextSummary] = Field(None, description="Resolved policy context summary")


class ExplainResponse(BaseModel):
    """Structured result returned by AI Service to Backend."""

    model_config = ConfigDict(from_attributes=True)

    question: str
    answer: str
    confidence: str
    status: str
    evidence: list[EvidenceItemSchema] = Field(default_factory=list)
    citations: list[CitationItem] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    guardrail_status: str = "passed"
    grounding_context: str = ""
    raw_llm_response: str = ""
