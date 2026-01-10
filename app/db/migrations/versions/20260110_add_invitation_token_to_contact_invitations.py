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
    op.add_column(
        'contact_invitations',
        sa.Column('invitation_token', sa.String(length=100), nullable=True)
    )
    op.create_unique_constraint(
        'uq_contact_invitations_invitation_token',
        'contact_invitations',
        ['invitation_token']
    )
    op.create_index(
        op.f('ix_contact_invitations_invitation_token'),
        'contact_invitations',
        ['invitation_token'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_contact_invitations_invitation_token'), table_name='contact_invitations')
    op.drop_constraint('uq_contact_invitations_invitation_token', 'contact_invitations', type_='unique')
    op.drop_column('contact_invitations', 'invitation_token')
