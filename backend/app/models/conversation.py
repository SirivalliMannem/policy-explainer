"""SQLAlchemy models for employee conversations and pre-RAG question history."""

from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    questions: Mapped[list[ConversationQuestion]] = relationship(
        "ConversationQuestion",
        back_populates="conversation",
        order_by="ConversationQuestion.created_at.asc()",
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
