"""Schemas for AI Policy Explainer answers, evidence, and citations."""

from datetime import date, datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.conversation import PolicyContextSummary


class CitationItem(BaseModel):
    """Citation referencing grounded policy source metadata."""

    model_config = ConfigDict(from_attributes=True)

    source_id: Optional[str] = None
    source_type: Optional[str] = None
    evidence_index: Optional[int] = None
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
    evidence_index: Optional[int] = None
    scope: Optional[str] = None  # customer_form | product_wording | policy_record


class GuardrailCheck(BaseModel):
    """Result of one deterministic guardrail check executed by the AI service."""

    name: str
    status: str  # passed | warning | failed
    detail: str = ""


class PortfolioPolicy(BaseModel):
    """One policy listed in a customer or portfolio answer (its current term)."""

    policy_id: str
    policy_number: str
    customer_id: str
    customer_name: str
    line_of_business: str
    product_name: Optional[str] = None
    status: str
    state: Optional[str] = None
    term_number: int
    effective_date: date
    expiration_date: date
    earlier_terms: int = 0


class PortfolioAnswer(BaseModel):
    """Facts read from policy records for a customer, household or whole-book question."""

    scope: str  # customer | household | book | not_found
    customers: list[str] = []
    filters: dict[str, str] = {}
    policies: list[PortfolioPolicy] = []


class QuestionAnswerResponse(BaseModel):
    """Structured answer response produced by the Policy Explainer pipeline."""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: str
    question_id: str
    question: str
    answer: str
    # policy_explanation: grounded answer about one policy's wording
    # portfolio: customer / book facts read from policy records (no language model)
    answer_type: str = "policy_explanation"
    portfolio: Optional[PortfolioAnswer] = None
    policy_context: Optional[PolicyContextSummary] = None
    evidence: list[EvidenceItemSchema] = []
    citations: list[CitationItem] = []
    confidence: str = "high"
    status: str = "answered"
    suggested_questions: list[str] = []
    guardrail_status: str = "passed"
    guardrail_checks: list[GuardrailCheck] = []
    outcome: str = "answered"
    model_used: str = "none"
    provider: str = "none"
    is_fallback: bool = False
    fallback_reason: Optional[str] = None
    retrieval: dict[str, Any] = {}
    timings_ms: dict[str, int] = {}
    latency_ms: Optional[int] = None
    ledger_id: Optional[str] = None


class ConversationMessage(BaseModel):
    """A recorded question and, when the pipeline produced one, its ledger-backed answer."""

    question_id: str
    question: str
    status: str
    policy_id: Optional[str] = None
    created_at: datetime
    answer: Optional[QuestionAnswerResponse] = None


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
    guardrail_checks: list[GuardrailCheck] = Field(default_factory=list)
    grounding_context: str = ""
    raw_llm_response: str = ""
    model_used: str = "none"
    provider: str = "none"
    is_fallback: bool = False
    fallback_reason: Optional[str] = None
    retrieval: dict[str, Any] = Field(default_factory=dict)
    timings_ms: dict[str, int] = Field(default_factory=dict)
