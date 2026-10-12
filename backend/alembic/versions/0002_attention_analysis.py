"""Add attention_analysis and resolution columns to evidence_ledger.

Revision ID: 0002_attention_analysis
Revises: 0001_baseline
Create Date: 2026-10-09
"""

from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0002_attention_analysis"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("evidence_ledger", sa.Column("attention_analysis", sa.JSON(), nullable=True))
    op.add_column(
        "evidence_ledger",
        sa.Column("is_resolved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("evidence_ledger", sa.Column("resolved_at", sa.DateTime(), nullable=True))
    op.add_column("evidence_ledger", sa.Column("resolved_by", sa.String(100), nullable=True))
    op.create_index("ix_evidence_ledger_is_resolved", "evidence_ledger", ["is_resolved"])


def downgrade() -> None:
    op.drop_index("ix_evidence_ledger_is_resolved", table_name="evidence_ledger")
    op.drop_column("evidence_ledger", "resolved_by")
    op.drop_column("evidence_ledger", "resolved_at")
    op.drop_column("evidence_ledger", "is_resolved")
    op.drop_column("evidence_ledger", "attention_analysis")
