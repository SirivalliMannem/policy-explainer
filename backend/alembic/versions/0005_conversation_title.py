"""Conversation title column.

The Conversation model gained an optional `title` (commit 6b831a4) without a migration, so every
query on `conversation` failed against an existing database. Nullable: existing conversations keep
their derived titles.

Revision ID: 0005_conversation_title
Revises: 0004_context_switch_audit
Create Date: 2026-10-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_conversation_title"
down_revision: str | None = "0004_context_switch_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversation", sa.Column("title", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("conversation", "title")
