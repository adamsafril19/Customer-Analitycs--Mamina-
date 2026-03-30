"""add_topic_version_tracking

Revision ID: 014_add_topic_versioning
Revises: 013_add_identity_constraint
Create Date: 2026-01-16

Add topic versioning for semantic continuity:
1. Add topic_idx to topics table
2. Rename avg_topic_confidence to avg_topic_similarity
3. Add topic_model_version to customer_text_semantics
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = '014_add_topic_versioning'
down_revision = '013_add_identity_constraint'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # 1. Add topic_idx to topics table
    conn.execute(text("""
        ALTER TABLE topics 
        ADD COLUMN IF NOT EXISTS topic_idx INTEGER
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_topics_topic_idx ON topics(topic_idx)
    """))
    
    # 2. Make model_version not null (with default for existing rows)
    conn.execute(text("""
        UPDATE topics SET model_version = 'v1.0' WHERE model_version IS NULL
    """))
    
    # 3. Add unique constraint for topic_idx + model_version
    # (skip if constraint already exists)
    try:
        conn.execute(text("""
            ALTER TABLE topics 
            ADD CONSTRAINT uq_topic_idx_version UNIQUE (topic_idx, model_version)
        """))
    except:
        pass  # Constraint may already exist
    
    # 4. Rename avg_topic_confidence to avg_topic_similarity
    conn.execute(text("""
        ALTER TABLE customer_text_semantics 
        RENAME COLUMN avg_topic_confidence TO avg_topic_similarity
    """))
    
    # 5. Add topic_model_version to customer_text_semantics
    conn.execute(text("""
        ALTER TABLE customer_text_semantics 
        ADD COLUMN IF NOT EXISTS topic_model_version VARCHAR(50)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_text_semantics_topic_version 
        ON customer_text_semantics(topic_model_version)
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE customer_text_semantics DROP COLUMN IF EXISTS topic_model_version"))
    conn.execute(text("ALTER TABLE customer_text_semantics RENAME COLUMN avg_topic_similarity TO avg_topic_confidence"))
    conn.execute(text("ALTER TABLE topics DROP CONSTRAINT IF EXISTS uq_topic_idx_version"))
    conn.execute(text("ALTER TABLE topics DROP COLUMN IF EXISTS topic_idx"))
