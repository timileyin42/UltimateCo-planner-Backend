"""Change default event status to confirmed

Revision ID: 20260121_change_status
Revises: 20260112_remove_biometric
Create Date: 2026-01-21 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260121_change_status'
down_revision = '20260112_remove_biometric'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Change default event status to confirmed and update existing drafts"""
    conn = op.get_bind()
    
    # 1. Update existing 'draft' events to 'confirmed'
    # We do this first so they match the new default
    conn.execute(sa.text("""
        UPDATE events 
        SET status = 'confirmed' 
        WHERE status = 'draft'
    """))
    
    # 2. Change the default value of the status column
    op.alter_column('events', 'status',
               existing_type=sa.String(length=50),
               server_default='confirmed',
               existing_nullable=False)


def downgrade() -> None:
    """Revert default event status to draft"""
    # 1. Revert the default value of the status column
    op.alter_column('events', 'status',
               existing_type=sa.String(length=50),
               server_default='draft',
               existing_nullable=False)
    
    # We do not revert the data update as we can't distinguish 
    # which ones were originally drafts vs confirmed.
