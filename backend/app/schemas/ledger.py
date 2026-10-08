"""Schemas for the Evidence Ledger audit views ("The Record")."""

from datetime import date, datetime
from typing import Any, Optional
from pydantic import BaseModel

from app.schemas.explainer import CitationItem, EvidenceItemSchema, GuardrailCheck


class LedgerSummary(BaseModel):
    answers_recorded: int
    carrier_source_count: int
    carrier_source_pct: float
    resolved_without_person_count: int
    resolved_without_person_pct: float
    p95_response_ms: Optional[int] = None
    waiting_on_person: int
    model_answers: int
    fallback_answers: int


class LedgerRow(BaseModel):
    id: str
    created_at: datetime
    conversation_id: str
    question_id: str
    agent: Optional[str] = None
    insured: Optional[str] = None
    customer_id: Optional[str] = None
    policy_id: Optional[str] = None
    answer_type: str = "policy_explanation"
    policy_number: Optional[str] = None
    policy_term: Optional[int] = None
    policy_effective: Optional[date] = None
    policy_expiration: Optional[date] = None
    state: Optional[str] = None
    line_of_business: Optional[str] = None
    question: str
    sources: list[str] = []
    source_count: int = 0
    model_used: Optional[str] = None
    provider: Optional[str] = None
    is_fallback: Optional[bool] = None
    confidence: str
    guardrail_status: str
    outcome: str
    reviewer: Optional[str] = None
    latency_ms: Optional[int] = None


class LedgerPage(BaseModel):
    items: list[LedgerRow]
    total: int
    limit: int
    offset: int


class LedgerFilterOption(BaseModel):
    value: str
    label: str


class LedgerFilters(BaseModel):
    insureds: list[LedgerFilterOption]
    states: list[str]
    lines: list[str]
    outcomes: list[str]


class LedgerDetail(LedgerRow):
    answer: str
    product_name: Optional[str] = None
    evidence: list[EvidenceItemSchema] = []
    citations: list[CitationItem] = []
    guardrail_checks: list[GuardrailCheck] = []
    suggested_questions: list[str] = []
    fallback_reason: Optional[str] = None
    retrieval: dict[str, Any] = {}
    timings_ms: dict[str, int] = {}
