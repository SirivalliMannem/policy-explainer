"""Pydantic schemas for Policy Explainer dashboard analytics."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


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
    # The verified policy, so a suggestion can be asked in a new conversation with the same context.
    policy_id: Optional[str] = None
    insured: Optional[str] = None
    line_of_business: Optional[str] = None
    times_asked: int
    first_asked_at: datetime
    last_asked_at: datetime
    latest_entry_id: str
    sources: AttentionSources
    # The stored analysis (classification, verified suggestions, what is missing); None until analysed.
    analysis: Optional[dict] = None
    analysis_entry_id: Optional[str] = None
    # Set when this item is a re-asked question that was flagged again: {entry_id, question}.
    rerun_of: Optional[dict] = None


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
    # Flagged questions in the range already resolved by a person (not in the queue).
    questions_resolved: int = 0
    items: List[AttentionItem]
    causes: List[AttentionCause]


class AttentionResolveRequest(BaseModel):
    """Close the flagged item whose latest ledger entry is entry_id.

    asked_suggestion: ask one of the stored, verified suggestions (question must match it).
    edited_and_asked: ask an edited question. dismissed: close it, with a reason (required).
    resolved: the employee resolved the original issue (for example by asking a suggestion in the
    chat); a note saying how is required.
    """
    entry_id: str
    action: str
    question: Optional[str] = Field(None, max_length=500)
    reason: Optional[str] = Field(None, max_length=2000)


class AttentionResolution(BaseModel):
    id: str
    question: str
    reason: str
    action: str
    action_label: str
    note: str = ""
    latest_entry_id: str
    new_question: Optional[str] = None
    new_entry_id: Optional[str] = None
    resolved_by: str
    resolved_by_name: Optional[str] = None
    resolved_by_role: Optional[str] = None
    resolved_at: datetime


class NewAnswer(BaseModel):
    """The answer to the question asked to close an item."""
    ledger_id: str
    conversation_id: str
    outcome: str
    # Flagged again: it appears in the queue as a new item marked as a re-run of the original.
    flagged: bool


class AttentionResolveResponse(BaseModel):
    resolution: AttentionResolution
    new_answer: Optional[NewAnswer] = None
