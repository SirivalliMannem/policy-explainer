"""Suggestion-based resolving: record the question asked to close a flagged item.

A flagged item is closed by asking a verified suggestion (or an edited question) as a new
question, by adding a missing edition, or by dismissing it. The closure records the new question
and the new answer's ledger id. The original flagged ledger record is never modified.

Revision ID: 0007_resolution_rerun
Revises: 0006_attention_resolution
Create Date: 2026-10-15
"""

from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0007_resolution_rerun"
down_revision: str | None = "0006_attention_resolution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("attention_resolution", sa.Column("new_question", sa.Text(), nullable=True))
    op.add_column("attention_resolution", sa.Column("new_entry_id", sa.String(36), nullable=True))
    op.create_index("ix_attention_resolution_new_entry_id", "attention_resolution", ["new_entry_id"])


def downgrade() -> None:
    op.drop_index("ix_attention_resolution_new_entry_id", table_name="attention_resolution")
    op.drop_column("attention_resolution", "new_entry_id")
    op.drop_column("attention_resolution", "new_question")
