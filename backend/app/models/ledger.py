"""SQLAlchemy model for the Evidence Ledger."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EvidenceLedger(Base):
    """Structured, traceable record connecting question, policy, evidence, and answer."""

    __tablename__ = "evidence_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), index=True)
    question_id: Mapped[str] = mapped_column(String(36), index=True)
    # Empty for customer / portfolio answers, which are not about one policy.
    policy_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    question: Mapped[str] = mapped_column(Text)
    retrieved_evidence: Mapped[list] = mapped_column(JSON, default=list)
    grounding_context: Mapped[str] = mapped_column(Text, default="")
    raw_llm_response: Mapped[str] = mapped_column(Text, default="")
    final_answer: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[str] = mapped_column(String(20), default="high")
    guardrail_status: Mapped[str] = mapped_column(String(30), default="passed")
    suggested_questions: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    # Audit detail for "The Record". Nullable so rows written before these columns existed
    # remain valid when Alembic adds them.
    employee_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    outcome: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    guardrail_checks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_fallback: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timings_ms: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retrieval: Mapped[dict | None] = mapped_column(JSON, nullable=True)
