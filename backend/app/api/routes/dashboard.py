"""Dashboard aggregation endpoints for Policy Explainer metrics and analytics."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.recent_questions import recent_questions
from app.models.conversation import Conversation, ConversationQuestion
from app.models.ledger import EvidenceLedger
from app.models.policy import CoreAccount, CoreForm, CorePolicy
from app.schemas.dashboard import (
    ActivityDataPoint,
    DashboardMetrics,
    DashboardResponse,
    EvidenceQualityBreakdown,
    RecentQuestionItem,
    TopicItem,
    TopicsResponse,
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
    recent_items = recent_questions(db, limit=10)

    return DashboardResponse(
        metrics=metrics,
        activity=activity_points,
        evidence_quality=evidence_quality,
        recent_questions=recent_items,
    )


def _window_start(time_range: str, now: datetime) -> datetime:
    """Same windows as the activity chart: the last 24 hours, or N whole days including today."""
    if time_range == "today":
        return now - timedelta(hours=24)
    days = 7 if time_range == "7d" else 30
    return (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/topics", response_model=TopicsResponse)
def get_most_asked_topics(
    time_range: str = Query("7d", alias="range", pattern="^(today|7d|30d)$"),
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """The policy forms most often cited in answers, each answer counted once per form.

    Portfolio answers (policy-record lookups) cite no form and are not counted.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    entries = (
        db.query(EvidenceLedger.citations, EvidenceLedger.retrieval)
        .filter(EvidenceLedger.created_at >= _window_start(time_range, now))
        .all()
    )

    counts: dict[str, int] = {}
    considered = 0
    for citations, retrieval in entries:
        if (retrieval or {}).get("answer_type") == "portfolio":
            continue
        forms = {c.get("form_number") for c in (citations or []) if c.get("form_number")}
        if not forms:
            continue
        considered += 1
        for form in forms:
            counts[form] = counts.get(form, 0) + 1

    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    titles = {
        number: (title, line)
        for number, title, line in db.query(CoreForm.form_number, CoreForm.title, CoreForm.line_of_business)
        .filter(CoreForm.form_number.in_([n for n, _ in ranked]))
        .all()
    }
    return TopicsResponse(
        range=time_range,
        answers_considered=considered,
        forms_cited=len(counts),
        topics=[
            TopicItem(
                form_number=number,
                title=titles.get(number, (number, None))[0],
                line_of_business=titles.get(number, (None, None))[1],
                count=count,
                share_pct=round(count / considered * 100, 1) if considered else 0.0,
            )
            for number, count in ranked
        ],
    )
