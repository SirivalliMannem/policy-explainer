"""SQLAlchemy model for the Evidence Ledger."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, JSON, String, Text
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
    policy_id: Mapped[str] = mapped_column(String(36), index=True)
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
