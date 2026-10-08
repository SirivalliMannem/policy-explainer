"""Pydantic schemas for Policy Explainer dashboard analytics."""

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
