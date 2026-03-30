"""add_link_status_enum

Revision ID: 017_add_link_status
Revises: 016_add_provisional_flag
Create Date: 2026-01-16

Add link_status column to feedback_linked for clearer identity resolution states.
Values: verified, probable, provisional, rejected
"""
from alembic import op
from sqlalchemy import text

revision = '017_add_link_status'
down_revision = '016_add_provisional_flag'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # Add link_status column
    conn.execute(text("""
        ALTER TABLE feedback_linked 
        ADD COLUMN IF NOT EXISTS link_status VARCHAR(20) DEFAULT 'provisional'
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_feedback_linked_status ON feedback_linked(link_status)
    """))
    
    # Set initial status based on confidence
    conn.execute(text("""
        UPDATE feedback_linked 
        SET link_status = CASE
            WHEN match_confidence >= 0.9 THEN 'probable'
            WHEN match_confidence >= 0.7 THEN 'probable'
            ELSE 'provisional'
        END
        WHERE link_status IS NULL OR link_status = 'provisional'
    """))
    
    # Add check constraint
    try:
        conn.execute(text("""
            ALTER TABLE feedback_linked 
            ADD CONSTRAINT chk_link_status 
            CHECK (link_status IN ('verified', 'probable', 'provisional', 'rejected'))
        """))
    except:
        pass  # Constraint may already exist


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE feedback_linked DROP CONSTRAINT IF EXISTS chk_link_status"))
    conn.execute(text("ALTER TABLE feedback_linked DROP COLUMN IF EXISTS link_status"))
