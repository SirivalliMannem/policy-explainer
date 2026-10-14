"""SQLAlchemy models for employee conversations and pre-RAG question history."""

from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Conversation(Base):
    """Employee conversation session tracking resolved policy context."""

    __tablename__ = "conversation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    employee_id: Mapped[str] = mapped_column(String(100), default="emp_demo_01", index=True)
    policy_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Archived conversations are hidden from their owner's lists, never deleted; their ledger
    # entries are unaffected and remain in The Record.
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    questions: Mapped[list[ConversationQuestion]] = relationship(
        "ConversationQuestion",
        back_populates="conversation",
        order_by="ConversationQuestion.created_at.asc()",
        cascade="all, delete-orphan",
    )
    context_switches: Mapped[list[ContextSwitchAudit]] = relationship(
        "ContextSwitchAudit",
        back_populates="conversation",
        order_by="ContextSwitchAudit.timestamp.asc()",
        cascade="all, delete-orphan",
    )


class ConversationQuestion(Base):
    """Questions recorded in a conversation before evidence retrieval / RAG."""

    __tablename__ = "conversation_question"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversation.id"), index=True
    )
    policy_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="ready_for_retrieval")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="questions")


class ContextSwitchAudit(Base):
    """Audit ledger tracking customer and policy context transitions within conversations."""

    __tablename__ = "context_switch_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversation.id"), index=True
    )
    employee_id: Mapped[str] = mapped_column(String(100), index=True)
    employee_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    employee_role: Mapped[str | None] = mapped_column(String(60), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    previous_customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    previous_customer_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    previous_policy_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    previous_policy_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    new_customer_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    new_policy_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    new_policy_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    switch_type: Mapped[str] = mapped_column(String(50))  # initial_selection | same_customer | different_customer | clear_context
    outcome: Mapped[str] = mapped_column(String(30))      # success | rejected | failed
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="context_switches")
