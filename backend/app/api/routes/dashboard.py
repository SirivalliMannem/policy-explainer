"""Dashboard aggregation endpoints for Policy Explainer metrics and analytics."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.conversation import Conversation, ConversationQuestion
from app.models.ledger import EvidenceLedger
from app.models.policy import CoreAccount, CorePolicy
from app.schemas.dashboard import (
    ActivityDataPoint,
    DashboardMetrics,
    DashboardResponse,
    EvidenceQualityBreakdown,
    RecentQuestionItem,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardResponse)
def get_dashboard_stats(
    time_range: str = Query("7d", alias="range", pattern="^(today|7d|30d)$"),
    db: Session = Depends(get_db),
):
    """Retrieve real aggregated dashboard metrics, activity history, evidence quality, and recent questions."""
    # 1. Core Metrics
    total_questions = db.query(ConversationQuestion).count()
    questions_answered = (
        db.query(ConversationQuestion)
        .filter(ConversationQuestion.status == "answered")
        .count()
    )
    resolution_rate = (
        round((questions_answered / total_questions) * 100, 1)
        if total_questions > 0
        else 0.0
    )

    # Evidence coverage: percentage of answered questions that contain validated evidence
    # EvidenceLedger records containing evidence
    answered_with_evidence = (
        db.query(EvidenceLedger)
        .filter(EvidenceLedger.confidence != "none")
        .count()
    )
    evidence_coverage = (
        min(round((answered_with_evidence / questions_answered) * 100, 1), 100.0)
        if questions_answered > 0
        else (100.0 if answered_with_evidence > 0 else 0.0)
    )

    # Low confidence questions: confidence in ('low', 'none') or status == 'insufficient_evidence'
    low_confidence_ledger = (
        db.query(EvidenceLedger)
        .filter(EvidenceLedger.confidence.in_(["low", "none"]))
        .count()
    )
    insufficient_questions = (
        db.query(ConversationQuestion)
        .filter(ConversationQuestion.status == "insufficient_evidence")
        .count()
    )
    low_confidence_count = max(low_confidence_ledger, insufficient_questions)

    metrics = DashboardMetrics(
        questions_answered=questions_answered,
        total_questions=total_questions,
        resolution_rate=resolution_rate,
        evidence_coverage=evidence_coverage,
        low_confidence=low_confidence_count,
    )

    # 2. Activity Time Series
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    activity_points: list[ActivityDataPoint] = []

    if time_range == "today":
        # Group by 3-hour or 4-hour intervals or hour buckets over the last 24h
        start_time = now - timedelta(hours=24)
        questions_window = (
            db.query(ConversationQuestion)
            .filter(ConversationQuestion.created_at >= start_time)
            .all()
        )
        # Create 8 3-hour slots
        slots = {}
        for h in range(0, 24, 3):
            slot_time = (start_time + timedelta(hours=h)).replace(minute=0, second=0, microsecond=0)
            slots[slot_time] = {"asked": 0, "answered": 0, "insufficient": 0}

        for q in questions_window:
            q_time = q.created_at.replace(minute=0, second=0, microsecond=0)
            # Find closest matching slot
            for slot_t in sorted(slots.keys(), reverse=True):
                if q_time >= slot_t:
                    slots[slot_t]["asked"] += 1
                    if q.status == "answered":
                        slots[slot_t]["answered"] += 1
                    elif q.status in ("insufficient_evidence", "low"):
                        slots[slot_t]["insufficient"] += 1
                    break

        for slot_t in sorted(slots.keys()):
            activity_points.append(
                ActivityDataPoint(
                    label=slot_t.strftime("%H:%M"),
                    timestamp=slot_t.isoformat(),
                    questions_asked=slots[slot_t]["asked"],
                    questions_answered=slots[slot_t]["answered"],
                    insufficient_evidence=slots[slot_t]["insufficient"],
                )
            )

    else:
        days_count = 7 if time_range == "7d" else 30
        start_date = (now - timedelta(days=days_count - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Pre-seed continuous days in range
        day_buckets = {}
        for d in range(days_count):
            day_t = start_date + timedelta(days=d)
            day_key = day_t.date()
            day_buckets[day_key] = {"asked": 0, "answered": 0, "insufficient": 0}

        questions_window = (
            db.query(ConversationQuestion)
            .filter(ConversationQuestion.created_at >= start_date)
            .all()
        )

        for q in questions_window:
            d_key = q.created_at.date()
            if d_key in day_buckets:
                day_buckets[d_key]["asked"] += 1
                if q.status == "answered":
                    day_buckets[d_key]["answered"] += 1
                elif q.status in ("insufficient_evidence", "low"):
                    day_buckets[d_key]["insufficient"] += 1

        for d_key in sorted(day_buckets.keys()):
            activity_points.append(
                ActivityDataPoint(
                    label=d_key.strftime("%b %d"),
                    timestamp=d_key.isoformat(),
                    questions_asked=day_buckets[d_key]["asked"],
                    questions_answered=day_buckets[d_key]["answered"],
                    insufficient_evidence=day_buckets[d_key]["insufficient"],
                )
            )

    # 3. Evidence Quality Breakdown
    high_count = (
        db.query(EvidenceLedger)
        .filter(EvidenceLedger.confidence == "high")
        .count()
    )
    medium_count = (
        db.query(EvidenceLedger)
        .filter(EvidenceLedger.confidence == "medium")
        .count()
    )
    low_count = (
        db.query(EvidenceLedger)
        .filter(EvidenceLedger.confidence.in_(["low", "none"]))
        .count()
    )
    total_ledger = high_count + medium_count + low_count

    evidence_quality = EvidenceQualityBreakdown(
        high=high_count,
        medium=medium_count,
        low=low_count,
        total=total_ledger,
    )

    # 4. Recent Policy Questions (Most recent 10)
    raw_recent = (
        db.query(
            ConversationQuestion,
            CorePolicy,
            CoreAccount,
            EvidenceLedger.confidence,
        )
        .outerjoin(CorePolicy, CorePolicy.id == ConversationQuestion.policy_id)
        .outerjoin(CoreAccount, CoreAccount.id == CorePolicy.account_id)
        .outerjoin(EvidenceLedger, EvidenceLedger.question_id == ConversationQuestion.id)
        .order_by(ConversationQuestion.created_at.desc())
        .limit(10)
        .all()
    )

    recent_items: list[RecentQuestionItem] = []
    for cq, policy, account, conf in raw_recent:
        cust_name = account.name if (account and account.name) else "Context pending"
        pol_num = policy.policy_number if (policy and policy.policy_number) else "Context pending"
        final_conf = conf if conf else ("none" if cq.status == "insufficient_evidence" else None)
        
        recent_items.append(
            RecentQuestionItem(
                question_id=cq.id,
                conversation_id=cq.conversation_id,
                question=cq.question,
                status=cq.status,
                confidence=final_conf,
                customer_name=cust_name,
                customer_id=account.id if account else None,
                policy_number=pol_num,
                policy_id=policy.id if policy else None,
                created_at=cq.created_at.isoformat(),
            )
        )

    return DashboardResponse(
        metrics=metrics,
        activity=activity_points,
        evidence_quality=evidence_quality,
        recent_questions=recent_items,
    )
