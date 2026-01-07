"""Add Google OAuth fields to users table

Revision ID: 67755e39be00
Revises: 80cb8398b4e3
Create Date: 2026-01-07 18:52:42.764655

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '67755e39be00'
down_revision = '80cb8398b4e3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add google_id column if it doesn't exist
    # Using raw SQL to safely check and add
    conn = op.get_bind()
    
    # Check if google_id column exists
    result = conn.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='google_id'
    """))
    if not result.fetchone():
        op.add_column('users', sa.Column('google_id', sa.String(length=255), nullable=True))
        op.create_index('ix_users_google_id', 'users', ['google_id'], unique=True)
    
    # Check if profile_picture_url column exists
    result = conn.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='profile_picture_url'
    """))
    if not result.fetchone():
        op.add_column('users', sa.Column('profile_picture_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    # Remove columns if they exist
    conn = op.get_bind()
    
    # Drop profile_picture_url if exists
    result = conn.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='profile_picture_url'
    """))
    if result.fetchone():
        op.drop_column('users', 'profile_picture_url')
    
    # Drop google_id and its index if exists
    result = conn.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='google_id'
    """))
    if result.fetchone():
        # Drop index first
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_users_google_id"))
        op.drop_column('users', 'google_id')
