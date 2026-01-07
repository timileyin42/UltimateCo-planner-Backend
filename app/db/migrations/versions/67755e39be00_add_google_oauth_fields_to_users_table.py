"""Add Google OAuth fields to users table

Revision ID: 67755e39be00
Revises: 80cb8398b4e3
Create Date: 2026-01-07 18:52:42.764655

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = '67755e39be00'
down_revision = '80cb8398b4e3'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(index_name, table_name):
    """Check if an index exists"""
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade() -> None:
    # Add google_id column (if not exists)
    if not column_exists('users', 'google_id'):
        op.add_column('users', sa.Column('google_id', sa.String(length=255), nullable=True))
    
    # Create index for google_id (if not exists)
    if not index_exists('ix_users_google_id', 'users'):
        op.create_index('ix_users_google_id', 'users', ['google_id'], unique=True)
    
    # Add profile_picture_url column (if not exists)
    if not column_exists('users', 'profile_picture_url'):
        op.add_column('users', sa.Column('profile_picture_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    # Remove profile_picture_url column (if exists)
    if column_exists('users', 'profile_picture_url'):
        op.drop_column('users', 'profile_picture_url')
    
    # Remove google_id index (if exists)
    if index_exists('ix_users_google_id', 'users'):
        op.drop_index('ix_users_google_id', table_name='users')
    
    # Remove google_id column (if exists)
    if column_exists('users', 'google_id'):
        op.drop_column('users', 'google_id')
