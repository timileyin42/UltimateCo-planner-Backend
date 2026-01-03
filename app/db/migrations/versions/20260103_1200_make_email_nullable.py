"""make email nullable for phone-only signup

Revision ID: 20260103_1200
Revises: 
Create Date: 2026-01-03 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260103_1200'
down_revision = '319423217dda'
branch_labels = None
depends_on = None

def upgrade():
    # make email nullable
    op.alter_column('users', 'email', existing_type=sa.String(length=255), nullable=True)


def downgrade():
    # revert to not null (will fail if nulls exist)
    op.alter_column('users', 'email', existing_type=sa.String(length=255), nullable=False)
