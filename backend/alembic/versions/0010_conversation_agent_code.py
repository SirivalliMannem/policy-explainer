"""Tag each conversation with the agent that owns it.

Revision ID: 0010_conversation_agent_code
Revises: 0009_conversation_customer_id
Create Date: 2026-10-21
"""

from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0010_conversation_agent_code"
down_revision: str | None = "0009_conversation_customer_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversation",
        sa.Column("agent_code", sa.String(10), nullable=False, server_default=sa.text("'A02'")),
    )
    op.create_index("ix_conversation_agent_code", "conversation", ["agent_code"])


def downgrade() -> None:
    op.drop_index("ix_conversation_agent_code", table_name="conversation")
    op.drop_column("conversation", "agent_code")
