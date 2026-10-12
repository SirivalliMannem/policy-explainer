"""Archive flag on conversations; asker name and role on evidence ledger entries.

Conversations are archived, never deleted: archiving only hides a conversation from its
owner's lists. Ledger entries are untouched by archiving and stay visible in The Record.
The ledger already stores employee_id; name and role are added as a snapshot of who asked
at the time. Existing rows keep NULL for both (shown as "not recorded"); nothing is backfilled.

Revision ID: 0003_archive_and_asker
Revises: 0002_attention_analysis
Create Date: 2026-10-12
"""

from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0003_archive_and_asker"
down_revision: str | None = "0002_attention_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversation",
        sa.Column("is_archived", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("conversation", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_conversation_employee_archived_updated",
        "conversation",
        ["employee_id", "is_archived", "updated_at"],
    )
    op.add_column("evidence_ledger", sa.Column("employee_name", sa.String(160), nullable=True))
    op.add_column("evidence_ledger", sa.Column("employee_role", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("evidence_ledger", "employee_role")
    op.drop_column("evidence_ledger", "employee_name")
    op.drop_index("ix_conversation_employee_archived_updated", table_name="conversation")
    op.drop_column("conversation", "archived_at")
    op.drop_column("conversation", "is_archived")
