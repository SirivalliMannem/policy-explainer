"""Pydantic schemas for Policy Explainer dashboard analytics."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    questions_answered: int
    total_questions: int
    resolution_rate: float
    evidence_coverage: float
    low_confidence: int


class ActivityDataPoint(BaseModel):
    label: str
    timestamp: str
    questions_asked: int
    questions_answered: int
    insufficient_evidence: int


class EvidenceQualityBreakdown(BaseModel):
    high: int
    medium: int
    low: int
    total: int


class RecentQuestionItem(BaseModel):
    question_id: str
    conversation_id: str
    question: str
    status: str
    confidence: Optional[str] = None
    customer_name: str = "Context pending"
    customer_id: Optional[str] = None
    policy_number: str = "Context pending"
    policy_id: Optional[str] = None
    created_at: str


class DashboardResponse(BaseModel):
    metrics: DashboardMetrics
    activity: List[ActivityDataPoint]
    evidence_quality: EvidenceQualityBreakdown
    recent_questions: List[RecentQuestionItem]


class TopicItem(BaseModel):
    form_number: str
    title: str
    line_of_business: Optional[str] = None
    count: int
    share_pct: float


class TopicsResponse(BaseModel):
    range: str
    answers_considered: int
    forms_cited: int = 0
    topics: List[TopicItem]


class AttentionSources(BaseModel):
    """What was searched (no-evidence answers) or cited (answers that were flagged)."""
    query_terms: List[str] = []
    coverages_searched: int = 0
    forms_searched: int = 0
    clauses_searched: int = 0
    citations: List[str] = []


class AttentionItem(BaseModel):
    """One flagged question, grouped across every time it was asked in the range."""
    question: str
    reason: str
    reason_label: str
    detail: str
    policy_number: Optional[str] = None
    insured: Optional[str] = None
    line_of_business: Optional[str] = None
    times_asked: int
    first_asked_at: datetime
    last_asked_at: datetime
    latest_entry_id: str
    sources: AttentionSources


class AttentionCause(BaseModel):
    reason: str
    label: str
    description: str
    count: int
    share_pct: float
    examples: List[str] = []


class AttentionResponse(BaseModel):
    range: str
    answers_total: int
    flagged_total: int
    questions_flagged: int
    items: List[AttentionItem]
    causes: List[AttentionCause]
