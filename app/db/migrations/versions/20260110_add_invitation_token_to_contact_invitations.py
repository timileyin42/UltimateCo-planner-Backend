"""add invitation_token to contact_invitations

Revision ID: 20260110_add_inv_token
Revises: 67755e39be00
Create Date: 2026-01-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260110_add_inv_token'
down_revision = '67755e39be00'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Add column if it does not exist
    col_exists = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'contact_invitations'
          AND column_name = 'invitation_token'
          AND table_schema = current_schema()
        LIMIT 1
    """)).scalar()

    if not col_exists:
        op.add_column(
            'contact_invitations',
            sa.Column('invitation_token', sa.String(length=100), nullable=True)
        )

    # Create unique constraint if missing
    uq_exists = conn.execute(sa.text("""
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_contact_invitations_invitation_token'
        LIMIT 1
    """)).scalar()
    if not uq_exists:
        op.create_unique_constraint(
            'uq_contact_invitations_invitation_token',
            'contact_invitations',
            ['invitation_token']
        )

    # Create index if missing
    ix_exists = conn.execute(sa.text("""
        SELECT 1 FROM pg_indexes
        WHERE schemaname = current_schema()
          AND tablename = 'contact_invitations'
          AND indexname = 'ix_contact_invitations_invitation_token'
        LIMIT 1
    """)).scalar()
    if not ix_exists:
        op.create_index(
            op.f('ix_contact_invitations_invitation_token'),
            'contact_invitations',
            ['invitation_token'],
            unique=False
        )


def downgrade() -> None:
    # Drop index, constraint, and column if they exist
    op.execute("DROP INDEX IF EXISTS ix_contact_invitations_invitation_token")
    op.execute("ALTER TABLE contact_invitations DROP CONSTRAINT IF EXISTS uq_contact_invitations_invitation_token")
    op.execute("ALTER TABLE contact_invitations DROP COLUMN IF EXISTS invitation_token")
