"""add_embedding_model_version

Revision ID: 019_add_embedding_version
Revises: 018_trusted_feedback_view
Create Date: 2026-01-16

Add embedding_model_version to feedback_features for semantic continuity.
Like sentiment and topic, embeddings change meaning with model changes.
"""
from alembic import op
from sqlalchemy import text

revision = '019_add_embedding_version'
down_revision = '018_trusted_feedback_view'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # Add embedding_model_version column
    conn.execute(text("""
        ALTER TABLE feedback_features 
        ADD COLUMN IF NOT EXISTS embedding_model_version VARCHAR(100)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_feedback_features_embedding_version 
        ON feedback_features(embedding_model_version)
    """))
    
    # Set default for existing rows
    conn.execute(text("""
        UPDATE feedback_features 
        SET embedding_model_version = 'paraphrase-multilingual-MiniLM-L12-v2|384'
        WHERE embedding IS NOT NULL AND embedding_model_version IS NULL
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE feedback_features DROP COLUMN IF EXISTS embedding_model_version"))
