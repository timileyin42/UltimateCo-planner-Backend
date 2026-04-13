"""add event invite token for permanent shareable links

Revision ID: 20260413_event_invite_token
Revises: 20260324_ai_plan_persist
Create Date: 2026-04-13 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260413_event_invite_token"
down_revision = "20260324_ai_plan_persist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("invite_token", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_events_invite_token", "events", ["invite_token"])
    op.create_index("idx_event_invite_token", "events", ["invite_token"])


def downgrade() -> None:
    op.drop_index("idx_event_invite_token", table_name="events")
    op.drop_constraint("uq_events_invite_token", "events", type_="unique")
    op.drop_column("events", "invite_token")
