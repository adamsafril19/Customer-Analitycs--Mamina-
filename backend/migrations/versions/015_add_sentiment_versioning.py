"""add_sentiment_versioning

Revision ID: 015_add_sentiment_versioning
Revises: 014_add_topic_versioning
Create Date: 2026-01-16

Add sentiment model versioning for semantic continuity.
Same pattern as topic versioning.
"""
from alembic import op
from sqlalchemy import text

revision = '015_add_sentiment_versioning'
down_revision = '014_add_topic_versioning'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # Add sentiment_model_version to customer_text_semantics
    conn.execute(text("""
        ALTER TABLE customer_text_semantics 
        ADD COLUMN IF NOT EXISTS sentiment_model_version VARCHAR(100)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_text_semantics_sentiment_version 
        ON customer_text_semantics(sentiment_model_version)
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE customer_text_semantics DROP COLUMN IF EXISTS sentiment_model_version"))
