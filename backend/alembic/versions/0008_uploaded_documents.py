"""Documents uploaded into a Policy Explainer conversation.

Only the extracted text is kept, one row per page (PDF) or section (Word/text), so answers can cite
the page they come from. The original file is discarded after extraction. A document belongs to the
conversation and employee that uploaded it; it is detached (is_active = false), never deleted.

Revision ID: 0008_uploaded_documents
Revises: 0007_resolution_rerun
Create Date: 2026-10-16
"""

from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0008_uploaded_documents"
down_revision: str | None = "0007_resolution_rerun"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uploaded_document",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversation.id"), nullable=False),
        sa.Column("employee_id", sa.String(100), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        # "page" for PDFs, "section" for Word and text files: how references are written.
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("detached_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_uploaded_document_conversation_id", "uploaded_document", ["conversation_id"])
    op.create_index("ix_uploaded_document_employee_id", "uploaded_document", ["employee_id"])

    op.create_table(
        "uploaded_document_page",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("uploaded_document.id"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
    )
    op.create_index("ix_uploaded_document_page_document_id", "uploaded_document_page", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_uploaded_document_page_document_id", table_name="uploaded_document_page")
    op.drop_table("uploaded_document_page")
    op.drop_index("ix_uploaded_document_employee_id", table_name="uploaded_document")
    op.drop_index("ix_uploaded_document_conversation_id", table_name="uploaded_document")
    op.drop_table("uploaded_document")
