"""Context switch audit ledger table.

Records every policy and customer context switch or transition within conversations:
who switched, when, previous customer/policy, new customer/policy, switch type, and outcome.

Revision ID: 0004_context_switch_audit
Revises: 0003_archive_and_asker
Create Date: 2026-10-12
"""

from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0004_context_switch_audit"
down_revision: str | None = "0003_archive_and_asker"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "context_switch_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversation.id"), nullable=False),
        sa.Column("employee_id", sa.String(100), nullable=False),
        sa.Column("employee_name", sa.String(160), nullable=True),
        sa.Column("employee_role", sa.String(60), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("previous_customer_id", sa.String(36), nullable=True),
        sa.Column("previous_customer_name", sa.String(160), nullable=True),
        sa.Column("previous_policy_id", sa.String(36), nullable=True),
        sa.Column("previous_policy_number", sa.String(32), nullable=True),
        sa.Column("new_customer_id", sa.String(36), nullable=True),
        sa.Column("new_customer_name", sa.String(160), nullable=True),
        sa.Column("new_policy_id", sa.String(36), nullable=True),
        sa.Column("new_policy_number", sa.String(32), nullable=True),
        sa.Column("switch_type", sa.String(50), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_context_switch_audit_conversation_id", "context_switch_audit", ["conversation_id"])
    op.create_index("ix_context_switch_audit_employee_id", "context_switch_audit", ["employee_id"])
    op.create_index("ix_context_switch_audit_timestamp", "context_switch_audit", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_context_switch_audit_timestamp", table_name="context_switch_audit")
    op.drop_index("ix_context_switch_audit_employee_id", table_name="context_switch_audit")
    op.drop_index("ix_context_switch_audit_conversation_id", table_name="context_switch_audit")
    op.drop_table("context_switch_audit")
