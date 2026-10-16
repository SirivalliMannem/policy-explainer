"""Documents uploaded into a conversation: extracted text only, one row per page or section."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UploadedDocument(Base):
    """A document uploaded by an employee into one of their conversations. Detached, never deleted."""

    __tablename__ = "uploaded_document"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversation.id"), index=True)
    employee_id: Mapped[str] = mapped_column(String(100), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int] = mapped_column(Integer)
    char_count: Mapped[int] = mapped_column(Integer)
    unit: Mapped[str] = mapped_column(String(20))  # page | section
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    detached_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class UploadedDocumentPage(Base):
    """The extracted text of one page (PDF) or section (Word, text)."""

    __tablename__ = "uploaded_document_page"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("uploaded_document.id"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
