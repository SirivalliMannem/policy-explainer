"""Resolutions for the Needs attention queue.

A flagged question (grouped by its wording and policy) is resolved by a person choosing an action.
The resolution is recorded here; the evidence-ledger entries it covers are never changed or
deleted. If the same question is asked again after it was resolved, it returns to the queue.

Revision ID: 0006_attention_resolution
Revises: 0005_conversation_title
Create Date: 2026-10-15
"""

from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0006_attention_resolution"
down_revision: str | None = "0005_conversation_title"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attention_resolution",
        sa.Column("id", sa.String(36), primary_key=True),
        # The queue groups by normalised question wording and policy; a resolution covers that group.
        sa.Column("question_key", sa.String(500), nullable=False),
        sa.Column("policy_id", sa.String(36), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        # The latest ledger entry when it was resolved (a reference only; the entry is not modified).
        sa.Column("latest_entry_id", sa.String(36), nullable=False),
        sa.Column("resolved_by", sa.String(100), nullable=False),
        sa.Column("resolved_by_name", sa.String(160), nullable=True),
        sa.Column("resolved_by_role", sa.String(60), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_attention_resolution_question_key", "attention_resolution", ["question_key"])
    op.create_index("ix_attention_resolution_policy_id", "attention_resolution", ["policy_id"])
    op.create_index("ix_attention_resolution_latest_entry_id", "attention_resolution", ["latest_entry_id"])
    op.create_index("ix_attention_resolution_resolved_at", "attention_resolution", ["resolved_at"])


def downgrade() -> None:
    op.drop_index("ix_attention_resolution_resolved_at", table_name="attention_resolution")
    op.drop_index("ix_attention_resolution_latest_entry_id", table_name="attention_resolution")
    op.drop_index("ix_attention_resolution_policy_id", table_name="attention_resolution")
    op.drop_index("ix_attention_resolution_question_key", table_name="attention_resolution")
    op.drop_table("attention_resolution")
