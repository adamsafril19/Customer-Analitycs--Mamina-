"""drop_semantic_from_feedback_features

Revision ID: 007_drop_semantic_cols
Revises: 006_drop_legacy_tables
Create Date: 2026-01-15

Remove semantic annotations from feedback_features.
"""
from alembic import op
from sqlalchemy import text

revision = '007_drop_semantic_cols'
down_revision = '006_drop_legacy_tables'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # Drop FK constraint
    conn.execute(text("""
        ALTER TABLE feedback_features 
        DROP CONSTRAINT IF EXISTS fk_feedback_features_topic
    """))
    
    # Drop semantic columns
    conn.execute(text("ALTER TABLE feedback_features DROP COLUMN IF EXISTS sentiment_score"))
    conn.execute(text("ALTER TABLE feedback_features DROP COLUMN IF EXISTS sentiment_label"))
    conn.execute(text("ALTER TABLE feedback_features DROP COLUMN IF EXISTS topic_id"))
    conn.execute(text("ALTER TABLE feedback_features DROP COLUMN IF EXISTS topic_confidence"))
    conn.execute(text("ALTER TABLE feedback_features DROP COLUMN IF EXISTS complaint_type"))
    conn.execute(text("ALTER TABLE feedback_features DROP COLUMN IF EXISTS keywords"))


def downgrade():
    pass
