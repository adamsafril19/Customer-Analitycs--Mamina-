"""add_is_provisional_to_customer

Revision ID: 016_add_provisional_flag
Revises: 015_add_sentiment_versioning
Create Date: 2026-01-16

Add is_provisional flag to customers table to mark auto-created "ghost" customers.
These should NOT be used for business aggregation until validated.
"""
from alembic import op
from sqlalchemy import text

revision = '016_add_provisional_flag'
down_revision = '015_add_sentiment_versioning'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # Add is_provisional column
    conn.execute(text("""
        ALTER TABLE customers 
        ADD COLUMN IF NOT EXISTS is_provisional BOOLEAN DEFAULT FALSE
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_customers_provisional ON customers(is_provisional)
    """))
    
    # Mark existing auto-created customers as provisional based on name pattern
    conn.execute(text("""
        UPDATE customers 
        SET is_provisional = TRUE 
        WHERE name LIKE 'Customer_%' OR name LIKE '[Provisional]%'
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE customers DROP COLUMN IF EXISTS is_provisional"))
