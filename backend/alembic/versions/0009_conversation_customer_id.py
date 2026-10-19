"""Add customer_id column to conversation table.

Revision ID: 0009_conversation_customer_id
Revises: 0008_uploaded_documents
Create Date: 2026-10-16
"""

from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0009_conversation_customer_id"
down_revision: str | None = "0008_uploaded_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversation", sa.Column("customer_id", sa.String(36), nullable=True))
    op.create_index("ix_conversation_customer_id", "conversation", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_conversation_customer_id", table_name="conversation")
    op.drop_column("conversation", "customer_id")
