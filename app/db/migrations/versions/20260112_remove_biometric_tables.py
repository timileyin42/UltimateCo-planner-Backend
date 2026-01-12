"""Remove biometric tables

Revision ID: 20260112_remove_biometric
Revises: 20260110_add_inv_token
Create Date: 2026-01-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260112_remove_biometric'
down_revision = '20260110_add_inv_token'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove biometric-related tables as mobile dev handles authentication client-side"""
    
    # Check if tables exist before dropping to ensure idempotency
    conn = op.get_bind()
    
    # Drop tables in reverse order of foreign key dependencies to avoid constraint errors
    # Order: biometric_auth_attempts -> biometric_tokens -> biometric_devices -> biometric_auths
    
    # 1. Drop biometric_auth_attempts (depends on biometric_auths)
    table_exists = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema()
            AND table_name = 'biometric_auth_attempts'
        )
    """)).scalar()
    
    if table_exists:
        op.drop_table('biometric_auth_attempts')
    
    # 2. Drop biometric_tokens (depends on biometric_devices)
    table_exists = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema()
            AND table_name = 'biometric_tokens'
        )
    """)).scalar()
    
    if table_exists:
        op.drop_table('biometric_tokens')
    
    # 3. Drop biometric_devices (depends on users)
    table_exists = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema()
            AND table_name = 'biometric_devices'
        )
    """)).scalar()
    
    if table_exists:
        op.drop_table('biometric_devices')
    
    # 4. Drop biometric_auths (depends on users)
    table_exists = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema()
            AND table_name = 'biometric_auths'
        )
    """)).scalar()
    
    if table_exists:
        op.drop_table('biometric_auths')


def downgrade() -> None:
    """Not recommended to recreate biometric tables - mobile handles auth now"""
    pass
