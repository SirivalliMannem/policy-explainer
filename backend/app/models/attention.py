"""Resolutions recorded for the Needs attention queue."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AttentionResolution(Base):
    """A person's decision on a flagged question. Ledger entries it covers are never changed."""

    __tablename__ = "attention_resolution"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    question_key: Mapped[str] = mapped_column(String(500), index=True)
    policy_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(40))
    note: Mapped[str] = mapped_column(Text, default="", server_default="")
    latest_entry_id: Mapped[str] = mapped_column(String(36), index=True)
    # The question asked to close the item and the ledger entry of its answer (asked actions only).
    new_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    resolved_by: Mapped[str] = mapped_column(String(100))
    resolved_by_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    resolved_by_role: Mapped[str | None] = mapped_column(String(60), nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, index=True)
