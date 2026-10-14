"""Read-only mapping of the carrier's knowledge library (owned and migrated by the seed models)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class KnowledgeCollection(Base):
    """A published set of company articles, scripts or procedures."""

    __tablename__ = "knowledge_collection"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(36), default="")
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(30), default="product_article")
    line_of_business: Mapped[str] = mapped_column(String(40), default="")
    state: Mapped[str] = mapped_column(String(2), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    version: Mapped[str] = mapped_column(String(20), default="1")
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class KnowledgeDocument(Base):
    """One approved article inside a knowledge collection."""

    __tablename__ = "knowledge_document"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(36), default="")
    collection_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_collection.id"))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    spoken: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[str] = mapped_column(String(20), default="1")
    approved_by: Mapped[str] = mapped_column(String(320), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
