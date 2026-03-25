"""add ai plan persistence fields

Revision ID: 20260324_ai_plan_persist
Revises: 20260121_change_status
Create Date: 2026-03-24 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260324_ai_plan_persist"
down_revision = "20260121_change_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("ai_plan_data", sa.Text(), nullable=True))

    op.add_column("ai_chat_sessions", sa.Column("plan_data", sa.Text(), nullable=True))
    op.add_column("ai_chat_sessions", sa.Column("llm_metadata", sa.Text(), nullable=True))

    op.add_column(
        "ai_chat_messages",
        sa.Column("message_type", sa.String(length=50), nullable=False, server_default="message"),
    )
    op.add_column("ai_chat_messages", sa.Column("tool_name", sa.String(length=255), nullable=True))
    op.add_column("ai_chat_messages", sa.Column("tool_call_id", sa.String(length=255), nullable=True))
    op.add_column("ai_chat_messages", sa.Column("tool_arguments", sa.Text(), nullable=True))
    op.add_column("ai_chat_messages", sa.Column("tool_result", sa.Text(), nullable=True))

    op.create_index(
        "idx_ai_chat_message_message_type",
        "ai_chat_messages",
        ["message_type"],
        unique=False,
    )
    op.create_index(
        "idx_ai_chat_message_tool_name",
        "ai_chat_messages",
        ["tool_name"],
        unique=False,
    )
    op.create_index(
        "idx_ai_chat_message_session_type",
        "ai_chat_messages",
        ["session_id", "message_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_ai_chat_message_session_type", table_name="ai_chat_messages")
    op.drop_index("idx_ai_chat_message_tool_name", table_name="ai_chat_messages")
    op.drop_index("idx_ai_chat_message_message_type", table_name="ai_chat_messages")

    op.drop_column("ai_chat_messages", "tool_result")
    op.drop_column("ai_chat_messages", "tool_arguments")
    op.drop_column("ai_chat_messages", "tool_call_id")
    op.drop_column("ai_chat_messages", "tool_name")
    op.drop_column("ai_chat_messages", "message_type")

    op.drop_column("ai_chat_sessions", "llm_metadata")
    op.drop_column("ai_chat_sessions", "plan_data")

    op.drop_column("events", "ai_plan_data")
